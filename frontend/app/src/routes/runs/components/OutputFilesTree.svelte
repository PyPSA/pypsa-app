<script lang="ts">
	import type { OutputFile, Workflow } from '$lib/types.js';
	import { runs } from '$lib/api/client.js';
	import { formatFileSize } from '$lib/utils.js';
	import { File, FileCode, FileTerminal, FileCog, FileBraces, FileSpreadsheet, FileBox, FileText, FileImage, FileArchive, Folder, FolderOpen, ChevronRight, Loader2 } from 'lucide-svelte';
	import { toast } from 'svelte-sonner';

	const EXT_ICONS: Record<string, typeof File> = {
		py: FileCode, sh: FileTerminal, bash: FileTerminal,
		yaml: FileCog, yml: FileCog,
		json: FileBraces, geojson: FileBraces,
		csv: FileSpreadsheet, tsv: FileSpreadsheet,
		nc: FileBox, h5: FileBox, hdf5: FileBox,
		log: FileText, txt: FileText,
		png: FileImage, jpg: FileImage, jpeg: FileImage, svg: FileImage, gif: FileImage,
		zip: FileArchive, tar: FileArchive, gz: FileArchive, tgz: FileArchive, bz2: FileArchive,
	};

	function fileIcon(name: string): typeof File {
		const ext = name.split('.').pop()?.toLowerCase() ?? '';
		return EXT_ICONS[ext] ?? File;
	}

	interface TreeNode {
		name: string;
		path: string;
		size: number;
		isDir: boolean;
		children: TreeNode[];
	}

	let { files, runId, workflow = null }: { files: OutputFile[]; runId: string; workflow?: Workflow | null } = $props();

	const SNAKEDISPATCH_PREFIX = /^\/app\/\.snakedispatch\/jobs\/[^/]+\//;

	const ruleMap = $derived.by(() => {
		const map = new Map<string, { rule: string; type: 'INPUT' | 'OUTPUT' }>();
		if (!workflow) return map;
		for (const rule of workflow.rules) {
			for (const job of rule.jobs ?? []) {
				for (const file of job.files ?? []) {
					if (file.file_type === 'INPUT' || file.file_type === 'OUTPUT') {
						const stripped = file.path.replace(SNAKEDISPATCH_PREFIX, '');
						const existing = map.get(stripped);
						// Prefer OUTPUT over INPUT (producing rule is more informative)
						if (!existing || (existing.type === 'INPUT' && file.file_type === 'OUTPUT')) {
							map.set(stripped, { rule: rule.name, type: file.file_type as 'INPUT' | 'OUTPUT' });
						}
					}
				}
			}
		}
		return map;
	});

	let expanded = $state(new Set<string>());
	let downloading = $state<string | null>(null);

	const tree = $derived.by(() => {
		const root: TreeNode[] = [];
		const dirs = new Map<string, TreeNode>();

		function ensureDir(dirPath: string): TreeNode[] {
			if (!dirPath) return root;
			if (dirs.has(dirPath)) return dirs.get(dirPath)!.children;

			const parts = dirPath.split('/');
			const parentPath = parts.slice(0, -1).join('/');
			const parent = ensureDir(parentPath);

			const node: TreeNode = {
				name: parts[parts.length - 1],
				path: dirPath,
				size: 0,
				isDir: true,
				children: [],
			};
			parent.push(node);
			dirs.set(dirPath, node);
			return node.children;
		}

		for (const file of files) {
			const lastSlash = file.path.lastIndexOf('/');
			const dirPath = lastSlash === -1 ? '' : file.path.slice(0, lastSlash);
			const fileName = lastSlash === -1 ? file.path : file.path.slice(lastSlash + 1);

			const parent = ensureDir(dirPath);
			parent.push({
				name: fileName,
				path: file.path,
				size: file.size,
				isDir: false,
				children: [],
			});
		}

		// Aggregate sizes up
		function aggregateSize(node: TreeNode): number {
			if (!node.isDir) return node.size;
			node.size = node.children.reduce((sum, c) => sum + aggregateSize(c), 0);
			return node.size;
		}

		// Sort: folders first, then alphabetical
		function sortNodes(nodes: TreeNode[]) {
			nodes.sort((a, b) => {
				if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
				return a.name.localeCompare(b.name);
			});
			for (const n of nodes) {
				if (n.isDir) sortNodes(n.children);
			}
		}

		for (const node of root) aggregateSize(node);
		sortNodes(root);
		return root;
	});

	// For each directory, if every file underneath shares the same tag, store it
	const dirTagMap = $derived.by(() => {
		const map = new Map<string, { rule: string; type: 'INPUT' | 'OUTPUT' } | 'mixed'>();
		// Group files by all ancestor directories
		for (const file of files) {
			const tag = ruleMap.get(file.path);
			const parts = file.path.split('/');
			for (let i = 1; i < parts.length; i++) {
				const dirPath = parts.slice(0, i).join('/');
				const existing = map.get(dirPath);
				if (existing === 'mixed') continue;
				if (!tag) continue;
				if (!existing) { map.set(dirPath, { rule: tag.rule, type: tag.type }); continue; }
				if (existing.rule !== tag.rule || existing.type !== tag.type) { map.set(dirPath, 'mixed'); }
			}
		}
		// Remove mixed entries
		for (const [key, val] of map) {
			if (val === 'mixed') map.delete(key);
		}
		return map as Map<string, { rule: string; type: 'INPUT' | 'OUTPUT' }>;
	});

	function toggle(path: string) {
		const next = new Set(expanded);
		if (next.has(path)) next.delete(path);
		else next.add(path);
		expanded = next;
	}

	async function download(node: TreeNode) {
		if (downloading) return;
		downloading = node.path;
		const url = runs.outputDownloadUrl(runId, node.path);
		try {
			const resp = await fetch(url, { credentials: 'include' });
			if (!resp.ok) {
				const detail = resp.status === 404 ? 'File is no longer available' : `Download failed: ${resp.status}`;
				toast.error(detail);
				return;
			}
			const blob = await resp.blob();
			const blobUrl = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = blobUrl;
			a.download = node.name;
			a.click();
			URL.revokeObjectURL(blobUrl);
		} catch {
			toast.error('Download failed');
		} finally {
			downloading = null;
		}
	}
</script>

{#snippet treeRow(node: TreeNode, depth: number)}
	{#if node.isDir}
		<button
			class="flex items-center gap-1.5 w-full text-left py-1 px-2 hover:bg-accent/50 rounded text-sm"
			style="padding-left: {depth * 1.25 + 0.5}rem"
			onclick={() => toggle(node.path)}
		>
			<ChevronRight
				class="h-3.5 w-3.5 text-muted-foreground shrink-0 transition-transform duration-150"
				style={expanded.has(node.path) ? 'transform: rotate(90deg)' : ''}
			/>
			{#if expanded.has(node.path)}
				<FolderOpen class="h-4 w-4 text-muted-foreground shrink-0" />
			{:else}
				<Folder class="h-4 w-4 text-muted-foreground shrink-0" />
			{/if}
			<span class="truncate">{node.name}</span>
			{#if !expanded.has(node.path) && dirTagMap.get(node.path)}
				{@const info = dirTagMap.get(node.path)!}
				<span class="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded-full shrink-0 ml-1.5">
					{info.type === 'INPUT' ? '→ ' : ''}{info.rule}{info.type === 'OUTPUT' ? ' →' : ''}
				</span>
			{/if}
			<span class="ml-auto text-xs text-muted-foreground shrink-0">{formatFileSize(node.size)}</span>
		</button>
		{#if expanded.has(node.path)}
			{#each node.children as child}
				{@render treeRow(child, depth + 1)}
			{/each}
		{/if}
	{:else}
		<button
			class="flex items-center gap-1.5 w-full text-left py-1 px-2 hover:bg-accent/50 rounded text-sm disabled:opacity-50"
			style="padding-left: {depth * 1.25 + 0.5 + 1.25}rem"
			onclick={() => download(node)}
			disabled={downloading !== null}
		>
			{#if downloading === node.path}
				<Loader2 class="h-4 w-4 text-muted-foreground shrink-0 animate-spin" />
			{:else}
				{@const Icon = fileIcon(node.name)}
				<Icon class="h-4 w-4 text-muted-foreground shrink-0" />
			{/if}
			<span class="truncate hover:underline">{node.name}</span>
			{#if ruleMap.get(node.path)}
				{@const info = ruleMap.get(node.path)!}
				<span class="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded-full shrink-0 ml-1.5">
					{info.type === 'INPUT' ? '→ ' : ''}{info.rule}{info.type === 'OUTPUT' ? ' →' : ''}
				</span>
			{/if}
			<span class="ml-auto text-xs text-muted-foreground shrink-0">{formatFileSize(node.size)}</span>
		</button>
	{/if}
{/snippet}

<div class="overflow-y-auto py-1" style="max-height: 60vh">
	{#each tree as node}
		{@render treeRow(node, 0)}
	{/each}
</div>
