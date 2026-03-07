<script lang="ts">
	import { authStore } from '$lib/stores/auth.svelte.js';
	import LoginForm from '$lib/components/login-form.svelte';

	let loading = $state(false);

	// Server guard handles redirect if already logged in

	function handleLogin() {
		loading = true;
		authStore.login();
	}
</script>

<svelte:head>
	<title>Login - PyPSA App</title>
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
				<LoginForm onclick={handleLogin} {loading} />
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
