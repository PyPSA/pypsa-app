<script lang="ts">
	import type { WorkflowRule, Rulegraph } from '$lib/types.js';
	import { formatDurationMs } from '$lib/utils.js';
	import ELK from 'elkjs/lib/elk.bundled.js';

	let {
		rulegraph,
		rules,
		activeLayers,
		onSelectRule
	}: {
		rulegraph: Rulegraph;
		rules: WorkflowRule[];
		activeLayers: Set<string>;
		onSelectRule: (name: string) => void;
	} = $props();

	interface LayoutNode { id: string; x: number; y: number; width: number; height: number }
	interface LayoutEdge { id: string; sections: { startPoint: { x: number; y: number }; endPoint: { x: number; y: number }; bendPoints?: { x: number; y: number }[] }[] }

	let layoutNodes = $state<LayoutNode[]>([]);
	let layoutEdges = $state<LayoutEdge[]>([]);
	let graphWidth = $state(0);
	let graphHeight = $state(0);

	const NODE_W = 160;
	const BASE_H = 40;
	const PADDING = 20;
	const MAX_LIST_ITEMS = 10;

	const ruleMap = $derived(new Map(rules.map(r => [r.name, r])));

	const SNAKEDISPATCH_PREFIX = /^(?:\/app\/)?\.snakedispatch\/(?:jobs\/)?[^/]+\//;

	function ruleOutputFiles(name: string): string[] {
		const rule = ruleMap.get(name);
		if (!rule) return [];
		const seen = new Set<string>();
		const files: string[] = [];
		for (const job of rule.jobs) {
			for (const f of job.files) {
				if (f.file_type === 'OUTPUT') {
					const cleaned = f.path.replace(SNAKEDISPATCH_PREFIX, '');
					if (!seen.has(cleaned)) {
						seen.add(cleaned);
						files.push(cleaned);
					}
				}
			}
		}
		return files;
	}

	function ruleDurationMs(name: string): number {
		const rule = ruleMap.get(name);
		if (!rule) return 0;
		let totalMs = 0;
		let count = 0;
		for (const job of rule.jobs) {
			if (job.started_at && job.end_time) {
				const ms = new Date(job.end_time).getTime() - new Date(job.started_at).getTime();
				if (ms > 0) { totalMs += ms; count++; }
			}
		}
		return count > 0 ? totalMs / count : 0;
	}

	const maxDuration = $derived(
		activeLayers.has('duration')
			? Math.max(...rules.map(r => ruleDurationMs(r.name)), 0)
			: 0
	);

	const SECTION_HEADER = 14;

	function cappedCount(total: number): number {
		return Math.min(total, MAX_LIST_ITEMS) + (total > MAX_LIST_ITEMS ? 1 : 0);
	}

	function nodeHeight(name: string): number {
		let h = BASE_H;
		if (activeLayers.has('wildcards')) {
			const count = ruleWildcards(name).length;
			if (count > 0) h += SECTION_HEADER + cappedCount(count) * 14;
		}
		if (activeLayers.has('files')) {
			const count = ruleOutputFiles(name).length;
			if (count > 0) h += SECTION_HEADER + cappedCount(count) * 14;
		}
		if (activeLayers.has('duration') && ruleDurationMs(name) > 0) h += SECTION_HEADER + 12 + 8;
		return h;
	}

	function nodeColor(name: string): string {
		const rule = ruleMap.get(name);
		if (!rule) return '#6b7280';
		if (rule.jobs_finished >= rule.total_job_count && rule.total_job_count > 0) return '#098754';
		if (rule.jobs_finished > 0) return '#eab308';
		return '#6b7280';
	}

	function ruleWildcards(name: string): string[] {
		const rule = ruleMap.get(name);
		if (!rule) return [];
		const seen = new Set<string>();
		const result: string[] = [];
		for (const job of rule.jobs) {
			if (job.wildcards) {
				const label = Object.entries(job.wildcards).map(([k, v]) => `${k}=${v}`).join(', ');
				if (label && !seen.has(label)) {
					seen.add(label);
					result.push(label);
				}
			}
		}
		return result;
	}

	let lastNodeKey = '';
	const elk = new ELK();

	$effect(() => {
		const layerKey = [...activeLayers].sort().join(',');
		const nodeKey = rulegraph.nodes.map(n => n.rule).join(',')
			+ '|' + rulegraph.links.map(l => `${l.sourcerule}-${l.targetrule}`).join(',')
			+ '|' + layerKey;
		if (nodeKey === lastNodeKey) return;
		lastNodeKey = nodeKey;

		const graph = {
			id: 'root',
			layoutOptions: {
				'elk.algorithm': 'layered',
				'elk.direction': 'RIGHT',
				'elk.spacing.nodeNode': '30',
				'elk.layered.spacing.nodeNodeBetweenLayers': '50',
			},
			children: rulegraph.nodes.map(n => ({
				id: n.rule,
				width: NODE_W,
				height: nodeHeight(n.rule),
			})),
			edges: rulegraph.links.map((l, i) => ({
				id: `e${i}`,
				sources: [l.sourcerule],
				targets: [l.targetrule],
			})),
		};

		elk.layout(graph).then(layout => {
			layoutNodes = (layout.children ?? []).map(n => ({
				id: n.id,
				x: (n.x ?? 0) + PADDING,
				y: (n.y ?? 0) + PADDING,
				width: n.width ?? NODE_W,
				height: n.height ?? nodeHeight(n.id),
			}));
			layoutEdges = ((layout.edges ?? []) as unknown as LayoutEdge[]).map(e => ({
				id: e.id,
				sections: e.sections,
			}));
			graphWidth = ((layout as unknown as { width: number }).width ?? 400) + PADDING * 2;
			graphHeight = ((layout as unknown as { height: number }).height ?? 200) + PADDING * 2;
		});
	});

	function edgePath(edge: LayoutEdge): string {
		if (!edge.sections || edge.sections.length === 0) return '';
		const s = edge.sections[0];
		let d = `M ${s.startPoint.x + PADDING} ${s.startPoint.y + PADDING}`;
		if (s.bendPoints) {
			for (const bp of s.bendPoints) {
				d += ` L ${bp.x + PADDING} ${bp.y + PADDING}`;
			}
		}
		d += ` L ${s.endPoint.x + PADDING} ${s.endPoint.y + PADDING}`;
		return d;
	}

	function truncate(text: string, maxLen: number): string {
		return text.length > maxLen ? text.slice(0, maxLen - 1) + '\u2026' : text;
	}
</script>

{#if layoutNodes.length > 0}
	<div class="overflow-x-auto">
		<svg width={graphWidth} height={graphHeight} class="block">
			<defs>
				<marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
					<polygon points="0 0, 8 3, 0 6" fill="#6b7280" />
				</marker>
			</defs>

			{#each layoutEdges as edge}
				<path
					d={edgePath(edge)}
					fill="none"
					stroke="#6b7280"
					stroke-width="1.5"
					marker-end="url(#arrowhead)"
				/>
			{/each}

			{#each layoutNodes as node}
				{@const hasLayers = activeLayers.size > 0}
				{@const labelY = hasLayers ? node.y + 16 : node.y + node.height / 2}
				<g
					class="cursor-pointer"
					onclick={() => onSelectRule(node.id)}
					role="button"
					tabindex="0"
					onkeydown={(e) => { if (e.key === 'Enter') onSelectRule(node.id); }}
				>
					<rect
						x={node.x}
						y={node.y}
						width={node.width}
						height={node.height}
						rx="6"
						fill={nodeColor(node.id)}
						opacity="0.15"
						stroke={nodeColor(node.id)}
						stroke-width="2"
					/>
					<text
						x={node.x + node.width / 2}
						y={labelY}
						text-anchor="middle"
						dominant-baseline="central"
						class="text-[11px] fill-foreground font-medium pointer-events-none"
					>
						{node.id}
					</text>

					{#if hasLayers}
						{@const baseY = node.y + 28}
						{@const wcAll = activeLayers.has('wildcards') ? ruleWildcards(node.id) : []}
						{@const wcShown = wcAll.slice(0, MAX_LIST_ITEMS)}
						{@const wcMore = wcAll.length - wcShown.length}
						{@const wcSectionH = wcAll.length > 0 ? SECTION_HEADER + cappedCount(wcAll.length) * 14 : 0}
						{@const filesAll = activeLayers.has('files') ? ruleOutputFiles(node.id) : []}
						{@const filesShown = filesAll.slice(0, MAX_LIST_ITEMS)}
						{@const filesMore = filesAll.length - filesShown.length}
						{@const filesSectionH = filesAll.length > 0 ? SECTION_HEADER + cappedCount(filesAll.length) * 14 : 0}
						{@const durationMs = activeLayers.has('duration') ? ruleDurationMs(node.id) : 0}

						{#if wcAll.length > 0}
							<text
								x={node.x + 8}
								y={baseY}
								dominant-baseline="hanging"
								class="text-[8px] fill-muted-foreground/60 pointer-events-none font-medium"
							>
								WILDCARDS
							</text>
							{#each wcShown as wc, i}
								<text
									x={node.x + 8}
									y={baseY + SECTION_HEADER + i * 14}
									dominant-baseline="hanging"
									class="text-[9px] fill-muted-foreground pointer-events-none"
								>
									{truncate(wc, 22)}
								</text>
							{/each}
							{#if wcMore > 0}
								<text
									x={node.x + 8}
									y={baseY + SECTION_HEADER + wcShown.length * 14}
									dominant-baseline="hanging"
									class="text-[9px] fill-muted-foreground/40 pointer-events-none italic"
								>
									+{wcMore} more
								</text>
							{/if}
						{/if}

						{#if filesAll.length > 0}
							{@const filesY = baseY + wcSectionH}
							<text
								x={node.x + 8}
								y={filesY}
								dominant-baseline="hanging"
								class="text-[8px] fill-muted-foreground/60 pointer-events-none font-medium"
							>
								FILES
							</text>
							{#each filesShown as file, i}
								<text
									x={node.x + 8}
									y={filesY + SECTION_HEADER + i * 14}
									dominant-baseline="hanging"
									class="text-[9px] fill-muted-foreground pointer-events-none"
								>
									• {truncate(file.split('/').pop() ?? file, 20)}
								</text>
							{/each}
							{#if filesMore > 0}
								<text
									x={node.x + 8}
									y={filesY + SECTION_HEADER + filesShown.length * 14}
									dominant-baseline="hanging"
									class="text-[9px] fill-muted-foreground/40 pointer-events-none italic"
								>
									+{filesMore} more
								</text>
							{/if}
						{/if}

						{#if durationMs > 0}
							{@const durY = baseY + wcSectionH + filesSectionH}
							{@const barMaxW = node.width - 16}
							{@const barW = maxDuration > 0 ? (durationMs / maxDuration) * barMaxW : 0}
							<text
								x={node.x + 8}
								y={durY}
								dominant-baseline="hanging"
								class="text-[8px] fill-muted-foreground/60 pointer-events-none font-medium"
							>
								DURATION
							</text>
							<text
								x={node.x + 8}
								y={durY + SECTION_HEADER}
								dominant-baseline="hanging"
								class="text-[9px] fill-muted-foreground pointer-events-none"
							>
								{rules.some(r => r.name === node.id && r.total_job_count > 1) ? 'ø ' : ''}{formatDurationMs(durationMs)}
							</text>
							<rect
								x={node.x + 8}
								y={durY + SECTION_HEADER + 14}
								width={barW}
								height={4}
								rx="2"
								fill={nodeColor(node.id)}
								opacity="0.5"
								class="pointer-events-none"
							/>
						{/if}

					{/if}
				</g>
			{/each}
		</svg>
	</div>
{/if}
