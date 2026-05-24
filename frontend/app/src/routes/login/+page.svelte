<script lang="ts">
	import { authStore } from '$lib/stores/auth.svelte.js';
	import LoginForm from './login-form.svelte';
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
			<div class="relative w-full max-w-xs">
				<LoginForm providers={authStore.providers} />
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
