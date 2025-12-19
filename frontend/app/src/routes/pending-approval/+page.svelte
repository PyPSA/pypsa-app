<script>
	import { authStore } from '$lib/stores/auth.svelte.js';
	import Button from '$lib/components/ui/button/button.svelte';

	// User data from server guard
	let { data } = $props();

	function handleLogout() {
		authStore.logout();
	}
</script>

<svelte:head>
	<title>Pending Approval - PyPSA App</title>
</svelte:head>

<div class="grid min-h-svh lg:grid-cols-2">
	<div class="flex flex-col gap-4 p-6 md:p-10">
		<div class="flex justify-center gap-2 md:justify-start">
			<a href="/" class="flex items-center gap-2 font-medium">
				<div class="flex size-8 items-center justify-center rounded-md">
					<img src="/pypsa-logo.svg" alt="PyPSA Logo" class="size-8" />
				</div>
				PyPSA App
			</a>
		</div>
		<div class="flex flex-1 items-center justify-center">
			<div class="w-full max-w-xs">
				<div class="flex flex-col gap-6">
					<div class="flex flex-col items-center gap-1 text-center">
						<h1 class="text-2xl font-bold">Account Pending Approval</h1>
						<p class="text-muted-foreground text-balance text-sm">
							Thank you for signing up, {data.user?.username}!
						</p>
					</div>

					<p class="text-center text-sm text-muted-foreground">
						Your account is pending approval by an administrator.
						You will be able to access the application once approved.
					</p>

					<Button variant="outline" onclick={handleLogout}>
						Sign Out
					</Button>
				</div>
			</div>
		</div>
	</div>
	<div class="bg-muted relative hidden lg:block overflow-hidden">
		<div class="absolute inset-0 flex items-center justify-center p-24">
			<img
				src="/pypsa-logo.svg"
				alt="PyPSA"
				class="w-full h-full object-contain"
			/>
		</div>
	</div>
</div>
