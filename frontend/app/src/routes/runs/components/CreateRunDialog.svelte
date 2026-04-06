<script lang="ts">
	import { runs } from '$lib/api/client.js';
	import type { BackendPublic, Run } from '$lib/types.js';
	import { Plus, X, Loader2, ChevronDown, Server, GitBranch, FileCode, Settings2 } from 'lucide-svelte';
	import Button from '$lib/components/ui/button/button.svelte';
	import Badge from '$lib/components/ui/badge/badge.svelte';
	import { toast } from 'svelte-sonner';
	import { goto } from '$app/navigation';

	let open = $state(false);
	let submitting = $state(false);
	let backends = $state<BackendPublic[]>([]);
	let loadingBackends = $state(false);
	let showAdvanced = $state(false);

	// Form fields
	let workflow = $state('');
	let gitRef = $state('');
	let configfile = $state('');
	let backendId = $state('');
	let snakemakeArgs = $state('');
	let importNetworks = $state('');
	let visibility = $state<'private' | 'public'>('private');

	// Validation
	let errors = $state<Record<string, string>>({});

	function validate(): boolean {
		errors = {};
		if (!workflow.trim()) {
			errors.workflow = 'Workflow URL is required';
		} else {
			try {
				new URL(workflow.trim());
			} catch {
				errors.workflow = 'Must be a valid URL (e.g., https://github.com/org/repo)';
			}
		}
		if (backends.length > 1 && !backendId) {
			errors.backend = 'Select a backend';
		}
		return Object.keys(errors).length === 0;
	}

	async function openDialog() {
		open = true;
		workflow = '';
		gitRef = '';
		configfile = '';
		backendId = '';
		snakemakeArgs = '';
		importNetworks = '';
		visibility = 'private';
		showAdvanced = false;
		errors = {};
		await loadBackends();
	}

	function closeDialog() {
		open = false;
	}

	async function loadBackends() {
		loadingBackends = true;
		try {
			backends = await runs.backends();
			// Auto-select if only one backend
			if (backends.length === 1) {
				backendId = backends[0].id;
			}
		} catch {
			backends = [];
		} finally {
			loadingBackends = false;
		}
	}

	async function handleSubmit() {
		if (!validate()) return;
		submitting = true;

		try {
			const body: Record<string, unknown> = {
				workflow: workflow.trim(),
				visibility,
			};

			if (gitRef.trim()) body.git_ref = gitRef.trim();
			if (configfile.trim()) body.configfile = configfile.trim();
			if (backendId) body.backend_id = backendId;

			if (snakemakeArgs.trim()) {
				body.snakemake_args = snakemakeArgs.trim().split(/\s+/).filter(Boolean);
			}
			if (importNetworks.trim()) {
				body.import_networks = importNetworks.trim().split(/[,\s]+/).filter(Boolean);
			}

			const run: Run = await runs.create(body as any);
			toast.success(`Run submitted`);
			closeDialog();
			goto(`/runs/${run.id}`);
		} catch (err: unknown) {
			toast.error((err as Error).message || 'Failed to submit run');
		} finally {
			submitting = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') closeDialog();
	}
</script>

<Button variant="default" size="sm" class="gap-1.5" onclick={openDialog}>
	<Plus size={14} />
	New Run
</Button>

{#if open}
	<div
		class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center"
		onclick={closeDialog}
		onkeydown={handleKeydown}
		role="dialog"
		tabindex="-1"
	>
		<div
			class="bg-card border border-border rounded-lg shadow-xl w-[520px] max-w-[90vw] max-h-[85vh] flex flex-col"
			onclick={(e) => e.stopPropagation()}
			role="document"
		>
			<!-- Header -->
			<div class="flex items-center justify-between p-4 border-b border-border shrink-0">
				<h3 class="font-semibold text-base">Submit New Run</h3>
				<button onclick={closeDialog} class="text-muted-foreground hover:text-foreground">
					<X size={16} />
				</button>
			</div>

			<!-- Body -->
			<div class="p-4 space-y-4 overflow-y-auto flex-1">
				<!-- Workflow URL -->
				<div>
					<label for="run-workflow" class="flex items-center gap-1.5 text-sm font-medium mb-1.5">
						<GitBranch size={14} class="text-muted-foreground" />
						Workflow
						<span class="text-destructive">*</span>
					</label>
					<input
						id="run-workflow"
						type="url"
						bind:value={workflow}
						placeholder="https://github.com/pypsa-meets-earth/pypsa-earth"
						class="w-full h-9 rounded-md border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring
							{errors.workflow ? 'border-destructive' : 'border-input'}"
					/>
					{#if errors.workflow}
						<p class="text-xs text-destructive mt-1">{errors.workflow}</p>
					{/if}
					<p class="text-xs text-muted-foreground mt-1">GitHub URL of the Snakemake workflow repository</p>
				</div>

				<!-- Git ref -->
				<div>
					<label for="run-gitref" class="flex items-center gap-1.5 text-sm font-medium mb-1.5">
						<GitBranch size={14} class="text-muted-foreground" />
						Branch / Tag
					</label>
					<input
						id="run-gitref"
						type="text"
						bind:value={gitRef}
						placeholder="main (default)"
						class="w-full h-9 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
					/>
				</div>

				<!-- Config file -->
				<div>
					<label for="run-config" class="flex items-center gap-1.5 text-sm font-medium mb-1.5">
						<FileCode size={14} class="text-muted-foreground" />
						Config File
					</label>
					<input
						id="run-config"
						type="text"
						bind:value={configfile}
						placeholder="config/config.yaml (optional)"
						class="w-full h-9 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
					/>
				</div>

				<!-- Backend -->
				{#if backends.length > 1}
					<div>
						<label for="run-backend" class="flex items-center gap-1.5 text-sm font-medium mb-1.5">
							<Server size={14} class="text-muted-foreground" />
							Backend
							<span class="text-destructive">*</span>
						</label>
						<select
							id="run-backend"
							bind:value={backendId}
							class="w-full h-9 rounded-md border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring
								{errors.backend ? 'border-destructive' : 'border-input'}"
						>
							<option value="">Select backend...</option>
							{#each backends as backend}
								<option value={backend.id}>
									{backend.name} {backend.is_active ? '' : '(inactive)'}
								</option>
							{/each}
						</select>
						{#if errors.backend}
							<p class="text-xs text-destructive mt-1">{errors.backend}</p>
						{/if}
					</div>
				{:else if backends.length === 1}
					<div class="flex items-center gap-2 text-sm text-muted-foreground">
						<Server size={14} />
						Backend: <Badge variant="secondary">{backends[0].name}</Badge>
					</div>
				{:else if loadingBackends}
					<div class="flex items-center gap-2 text-sm text-muted-foreground">
						<Loader2 size={14} class="animate-spin" />
						Loading backends...
					</div>
				{:else}
					<div class="text-sm text-destructive">
						No execution backends available. Contact an administrator.
					</div>
				{/if}

				<!-- Advanced toggle -->
				<button
					onclick={() => showAdvanced = !showAdvanced}
					class="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
				>
					<Settings2 size={14} />
					Advanced options
					<ChevronDown size={12} class="transition-transform {showAdvanced ? 'rotate-180' : ''}" />
				</button>

				{#if showAdvanced}
					<div class="space-y-4 pl-2 border-l-2 border-border">
						<!-- Snakemake args -->
						<div>
							<label for="run-args" class="text-sm font-medium mb-1.5 block">Snakemake Arguments</label>
							<input
								id="run-args"
								type="text"
								bind:value={snakemakeArgs}
								placeholder="--cores 4 --forceall"
								class="w-full h-9 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
							/>
							<p class="text-xs text-muted-foreground mt-1">Space-separated arguments passed to snakemake</p>
						</div>

						<!-- Import networks -->
						<div>
							<label for="run-import" class="text-sm font-medium mb-1.5 block">Import Networks</label>
							<input
								id="run-import"
								type="text"
								bind:value={importNetworks}
								placeholder="results/networks/*.nc (glob patterns)"
								class="w-full h-9 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
							/>
							<p class="text-xs text-muted-foreground mt-1">Glob patterns for network files to import after completion</p>
						</div>

						<!-- Visibility -->
						<div class="flex items-center gap-3">
							<label class="text-sm font-medium">Visibility:</label>
							<label class="flex items-center gap-1.5 text-sm cursor-pointer">
								<input type="radio" bind:group={visibility} value="private" class="accent-primary" />
								Private
							</label>
							<label class="flex items-center gap-1.5 text-sm cursor-pointer">
								<input type="radio" bind:group={visibility} value="public" class="accent-primary" />
								Public
							</label>
						</div>
					</div>
				{/if}
			</div>

			<!-- Footer -->
			<div class="flex justify-end gap-2 p-4 border-t border-border shrink-0">
				<Button variant="ghost" size="sm" onclick={closeDialog} disabled={submitting}>
					Cancel
				</Button>
				<Button variant="default" size="sm" onclick={handleSubmit} disabled={submitting || backends.length === 0}>
					{#if submitting}
						<Loader2 size={14} class="mr-1.5 animate-spin" />
						Submitting...
					{:else}
						<Plus size={14} class="mr-1.5" />
						Submit Run
					{/if}
				</Button>
			</div>
		</div>
	</div>
{/if}
