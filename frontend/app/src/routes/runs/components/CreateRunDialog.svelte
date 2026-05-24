<script lang="ts">
	import { onMount } from 'svelte';
	import { runs } from '$lib/api/client.js';
	import { fieldDescriptions } from '$lib/api/schema.js';
	import { toast } from 'svelte-sonner';
	import * as Dialog from '$lib/components/ui/dialog';
	import * as Select from '$lib/components/ui/select';
	import * as Tooltip from '$lib/components/ui/tooltip';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import Button from '$lib/components/ui/button/button.svelte';
	import Loader2 from '@lucide/svelte/icons/loader-2';
	import Info from '@lucide/svelte/icons/info';
	import type { BackendPublic } from '$lib/types.js';

	const FIELD_PATHS = [
		'workflow',
		'git_ref',
		'configfile',
		'backend_id',
		'visibility',
		'import_networks',
		'snakemake_args',
		'callback_url',
		'extra_files',
		'cache.key',
		'cache.dirs'
	];
	let descriptions = $state<Record<string, string>>({});

	let { open = $bindable(false), onCreated }: { open?: boolean; onCreated?: () => void } = $props();

	let workflow = $state('');
	let git_ref = $state('');
	let configfile = $state('');
	let backend_id = $state('');
	let isPublic = $state(false);
	let callback_url = $state('');
	let snakemake_args = $state('');
	let import_networks = $state('');
	let extra_files = $state('');
	let cache_key = $state('');
	let cache_dirs = $state('');

	let backends = $state<BackendPublic[]>([]);
	let backendsLoaded = $state(false);
	let submitting = $state(false);
	let extraFilesError = $state('');
	let workflowError = $state('');

	function validateWorkflow(s: string): string {
		const trimmed = s.trim();
		if (!trimmed) return '';
		try {
			const u = new URL(trimmed);
			if (u.protocol !== 'http:' && u.protocol !== 'https:') {
				return 'Workflow URL must use http or https';
			}
			return '';
		} catch {
			return 'Workflow must be a valid URL (e.g. https://github.com/PyPSA/pypsa-eur)';
		}
	}

	function autoSelectBackend() {
		const active = backends.filter((b) => b.is_active);
		if (active.length === 1) backend_id = active[0].id;
		else if (backends.length === 1) backend_id = backends[0].id;
	}

	async function loadBackends() {
		try {
			backends = await runs.backends();
			if (!backend_id) autoSelectBackend();
		} catch {
		} finally {
			backendsLoaded = true;
		}
	}

	onMount(() => {
		fieldDescriptions('RunCreate', FIELD_PATHS).then((d) => (descriptions = d));
	});

	// Refresh on each open so newly added/removed backends show up.
	$effect(() => {
		if (open) loadBackends();
	});

	function splitLines(s: string): string[] {
		return s
			.split('\n')
			.map((l) => l.trim())
			.filter((l) => l.length > 0);
	}

	function reset() {
		workflow = '';
		git_ref = '';
		configfile = '';
		isPublic = false;
		callback_url = '';
		snakemake_args = '';
		import_networks = '';
		extra_files = '';
		cache_key = '';
		cache_dirs = '';
		extraFilesError = '';
		workflowError = '';
		backend_id = '';
		autoSelectBackend();
	}

	async function submit() {
		if (!workflow.trim() || submitting) return;
		extraFilesError = '';

		workflowError = validateWorkflow(workflow);
		if (workflowError) return;

		const body: Parameters<typeof runs.create>[0] = { workflow: workflow.trim() };

		if (git_ref.trim()) body.git_ref = git_ref.trim();
		if (configfile.trim()) body.configfile = configfile.trim();
		if (backend_id) body.backend_id = backend_id;
		if (isPublic) body.visibility = 'public';
		if (callback_url.trim()) body.callback_url = callback_url.trim();

		const args = splitLines(snakemake_args);
		if (args.length > 0) body.snakemake_args = args;

		const networks = splitLines(import_networks);
		if (networks.length > 0) body.import_networks = networks;

		if (extra_files.trim()) {
			try {
				const parsed = JSON.parse(extra_files);
				if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
					extraFilesError = 'extra_files must be a JSON object';
					return;
				}
				body.extra_files = parsed as Record<string, string>;
			} catch (e) {
				extraFilesError = `Invalid JSON: ${(e as Error).message}`;
				return;
			}
		}

		if (cache_key.trim()) {
			body.cache = { key: cache_key.trim(), dirs: splitLines(cache_dirs) };
		}

		submitting = true;
		try {
			await runs.create(body);
			toast.success('Run created');
			reset();
			open = false;
			onCreated?.();
		} catch {
		} finally {
			submitting = false;
		}
	}

	const selectedBackendName = $derived(
		backends.find((b) => b.id === backend_id)?.name ?? 'Select backend...'
	);
</script>

{#snippet infoTip(text: string | undefined)}
	{#if text}
		<Tooltip.Root>
			<Tooltip.Trigger>
				{#snippet child({ props }: { props: Record<string, unknown> })}
					<span
						class="text-muted-foreground hover:text-foreground transition-colors inline-flex"
						{...props}
					>
						<Info class="h-3.5 w-3.5" />
					</span>
				{/snippet}
			</Tooltip.Trigger>
			<Tooltip.Content class="max-w-xs"><p>{text}</p></Tooltip.Content>
		</Tooltip.Root>
	{/if}
{/snippet}

<Dialog.Root bind:open>
	<Dialog.Content class="max-w-md max-h-[80vh] overflow-y-auto">
		<Dialog.Header>
			<Dialog.Title>Create Run</Dialog.Title>
			<Dialog.Description>Trigger a new workflow run.</Dialog.Description>
		</Dialog.Header>

		<div class="space-y-4">
			<div class="space-y-2">
				<div class="flex items-center gap-1.5">
					<Label for="run-workflow">Workflow <span class="text-destructive">*</span></Label>
					{@render infoTip(descriptions.workflow)}
				</div>
				<Input
					id="run-workflow"
					placeholder="https://github.com/PyPSA/pypsa-eur"
					bind:value={workflow}
					oninput={() => (workflowError = '')}
				/>
				{#if workflowError}
					<p class="text-xs text-destructive">{workflowError}</p>
				{/if}
			</div>

			<div class="space-y-2">
				<div class="flex items-center gap-1.5">
					<Label for="run-git-ref">Git ref</Label>
					{@render infoTip(descriptions.git_ref)}
				</div>
				<Input id="run-git-ref" placeholder="main" bind:value={git_ref} />
			</div>

			<div class="space-y-2">
				<div class="flex items-center gap-1.5">
					<Label for="run-configfile">Config file</Label>
					{@render infoTip(descriptions.configfile)}
				</div>
				<Input
					id="run-configfile"
					placeholder="config/config.yaml"
					bind:value={configfile}
				/>
			</div>

			{#if backendsLoaded && backends.length > 1}
				<div class="space-y-2">
					<div class="flex items-center gap-1.5">
						<Label>Backend</Label>
						{@render infoTip(descriptions.backend_id)}
					</div>
					<Select.Root type="single" bind:value={backend_id}>
						<Select.Trigger class="w-full">{selectedBackendName}</Select.Trigger>
						<Select.Content>
							{#each backends as b}
								<Select.Item value={b.id} disabled={!b.is_active}>
									{b.name}{!b.is_active ? ' (inactive)' : ''}
								</Select.Item>
							{/each}
						</Select.Content>
					</Select.Root>
				</div>
			{/if}

			<div class="flex items-center gap-2">
				<Checkbox id="run-public" bind:checked={isPublic} />
				<Label for="run-public">Public</Label>
				{@render infoTip(descriptions.visibility)}
			</div>

			<div class="space-y-2">
				<div class="flex items-center gap-1.5">
					<Label for="run-import-networks">Import networks <span class="text-muted-foreground font-normal">(one path per line)</span></Label>
					{@render infoTip(descriptions.import_networks)}
				</div>
				<textarea
					id="run-import-networks"
					rows="3"
					class="w-full rounded-md border bg-background px-3 py-2 text-sm font-mono"
					bind:value={import_networks}
				></textarea>
			</div>

			<details class="space-y-2">
				<summary class="text-sm font-medium cursor-pointer select-none">Advanced</summary>
				<div class="space-y-4 pt-3">
					<div class="space-y-2">
						<div class="flex items-center gap-1.5">
							<Label for="run-snakemake-args">Snakemake args <span class="text-muted-foreground font-normal">(one per line)</span></Label>
							{@render infoTip(descriptions.snakemake_args)}
						</div>
						<textarea
							id="run-snakemake-args"
							rows="3"
							class="w-full rounded-md border bg-background px-3 py-2 text-sm font-mono"
							placeholder="--cores 4&#10;--rerun-incomplete"
							bind:value={snakemake_args}
						></textarea>
					</div>

					<div class="space-y-2">
						<div class="flex items-center gap-1.5">
							<Label for="run-callback-url">Callback URL</Label>
							{@render infoTip(descriptions.callback_url)}
						</div>
						<Input
							id="run-callback-url"
							placeholder="https://example.com/hook"
							bind:value={callback_url}
						/>
					</div>

					<div class="space-y-2">
						<div class="flex items-center gap-1.5">
							<Label for="run-extra-files">extra_files <span class="text-muted-foreground font-normal">(JSON object)</span></Label>
							{@render infoTip(descriptions.extra_files)}
						</div>
						<textarea
							id="run-extra-files"
							rows="4"
							class="w-full rounded-md border bg-background px-3 py-2 text-sm font-mono"
							placeholder={'{"path/in/repo.yaml": "file contents"}'}
							bind:value={extra_files}
						></textarea>
						{#if extraFilesError}
							<p class="text-xs text-destructive">{extraFilesError}</p>
						{/if}
					</div>

					<div class="space-y-2">
						<div class="flex items-center gap-1.5">
							<Label for="run-cache-key">Cache key</Label>
							{@render infoTip(descriptions['cache.key'])}
						</div>
						<Input id="run-cache-key" bind:value={cache_key} />
					</div>

					<div class="space-y-2">
						<div class="flex items-center gap-1.5">
							<Label for="run-cache-dirs">Cache dirs <span class="text-muted-foreground font-normal">(one per line)</span></Label>
							{@render infoTip(descriptions['cache.dirs'])}
						</div>
						<textarea
							id="run-cache-dirs"
							rows="3"
							class="w-full rounded-md border bg-background px-3 py-2 text-sm font-mono"
							bind:value={cache_dirs}
						></textarea>
					</div>
				</div>
			</details>
		</div>

		<Dialog.Footer class="flex gap-2">
			<Button variant="outline" size="sm" onclick={() => (open = false)} disabled={submitting}>
				Cancel
			</Button>
			<Button size="sm" onclick={submit} disabled={!workflow.trim() || submitting}>
				{#if submitting}
					<Loader2 class="mr-1 size-4 animate-spin" />
				{/if}
				Create
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
