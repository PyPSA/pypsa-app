<script lang="ts">
	import { goto } from '$app/navigation';
	import { toast } from 'svelte-sonner';
	import { auth, type AuthProviderInfo } from '$lib/api/client.js';
	import { authStore } from '$lib/stores/auth.svelte.js';
	import { features } from '$lib/stores/features.svelte.js';
	import {
		FieldGroup,
		Field,
		FieldLabel,
		FieldSeparator,
	} from "$lib/components/ui/field/index.js";
	import { Input } from "$lib/components/ui/input/index.js";
	import { Button } from "$lib/components/ui/button/index.js";
	import { cn, type WithElementRef } from "$lib/utils.js";
	import type { HTMLFormAttributes } from "svelte/elements";
	import Chrome from '@lucide/svelte/icons/chrome';
	import LogIn from '@lucide/svelte/icons/log-in';
	import Eye from '@lucide/svelte/icons/eye';
	import EyeOff from '@lucide/svelte/icons/eye-off';

	let {
		ref = $bindable(null),
		class: className,
		providers = [],
		...restProps
	}: WithElementRef<HTMLFormAttributes> & {
		providers?: AuthProviderInfo[];
	} = $props();

	const id = $props.id();

	let loading = $state(false);
	let email = $state('');
	let password = $state('');
	let showPassword = $state(false);
	let errorMsg = $state<string | null>(null);

	// Mirror DEMO_EMAIL/DEMO_PASSWORD in src/pypsa_app/backend/auth/password.py.
	// One-shot latch so a user clearing the field is not overwritten.
	let demoPrefilled = false;
	$effect(() => {
		if (features.demoMode && !demoPrefilled) {
			demoPrefilled = true;
			email = 'demo@example.org';
			password = 'demopypsa';
		}
	});

	const PLACEHOLDER_OAUTH: AuthProviderInfo[] = [
		{ id: 'github', name: 'GitHub', type: 'oauth', login_url: undefined, icon: 'github' },
	];

	const hasCredentials = $derived(providers.some(p => p.type === 'credentials'));
	const realOauthProviders = $derived(providers.filter(p => p.type === 'oauth'));
	const oauthProviders = $derived(
		realOauthProviders.length > 0 ? realOauthProviders : PLACEHOLDER_OAUTH
	);
	const hasOAuth = $derived(oauthProviders.length > 0);

	function iconFor(icon?: string) {
		if (icon === 'chrome') return Chrome;
		return LogIn;
	}

	async function handlePasswordLogin(e: Event) {
		e.preventDefault();
		loading = true;
		errorMsg = null;
		try {
			await auth.passwordLogin(email, password);
			await authStore.refreshUser();
			goto('/networks');
		} catch (err) {
			errorMsg = (err as Error).message || 'Invalid credentials';
			loading = false;
		}
	}

	function startOAuth(p: AuthProviderInfo) {
		if (!p.login_url) {
			toast.error(`Login with ${p.name} is not available on the demo instance.`);
			return;
		}
		loading = true;
		window.location.href = p.login_url;
	}

	function handleForgotPassword(e: Event) {
		e.preventDefault();
		toast.error('Password recovery is not available on the demo instance.');
	}

	function handleSignUp(e: Event) {
		e.preventDefault();
		if (features.demoMode) {
			toast.error('Sign up is not available on the demo instance.');
		} else {
			toast.error('Sign up via the OAuth provider above.');
		}
	}
</script>

<form class={cn("flex flex-col gap-6", className)} bind:this={ref} {...restProps} onsubmit={handlePasswordLogin}>
	<FieldGroup>
		{#if hasCredentials}
			<div class="flex flex-col items-center gap-1 text-center">
				<h1 class="text-2xl font-bold">Login to your account</h1>
				<p class="text-muted-foreground text-balance text-sm">
					{#if features.demoMode}
						This is a public demo instance. It is regularly reset.
						Uploads to this instance are disabled.
						<br />
						Click Login to continue.
					{:else}
						Enter your email below to login to your account
					{/if}
				</p>
			</div>
			<Field>
				<FieldLabel for="email-{id}">Email</FieldLabel>
				<Input
					id="email-{id}"
					type="email"
					placeholder="you@example.com"
					bind:value={email}
					autocomplete={features.demoMode ? 'off' : undefined}
					required
				/>
			</Field>
			<Field>
				<div class="flex items-center">
					<FieldLabel for="password-{id}">Password</FieldLabel>
					<a
						href="##"
						onclick={handleForgotPassword}
						class="ml-auto text-sm text-muted-foreground underline-offset-4 hover:underline"
					>
						Forgot your password?
					</a>
				</div>
				<div class="relative">
					<Input
						id="password-{id}"
						type={showPassword ? 'text' : 'password'}
						bind:value={password}
						autocomplete={features.demoMode ? 'off' : undefined}
						class="pr-9"
						required
					/>
					<button
						type="button"
						onclick={() => (showPassword = !showPassword)}
						aria-label={showPassword ? 'Hide password' : 'Show password'}
						aria-pressed={showPassword}
						class="text-muted-foreground hover:text-foreground absolute inset-y-0 right-0 flex items-center px-3"
					>
						{#if showPassword}
							<EyeOff class="size-4" />
						{:else}
							<Eye class="size-4" />
						{/if}
					</button>
				</div>
			</Field>
			{#if errorMsg}
				<p class="text-destructive text-sm" role="alert">{errorMsg}</p>
			{/if}
			<Field>
				<Button type="submit" disabled={loading}>
					{loading ? 'Signing in...' : 'Login'}
				</Button>
			</Field>
		{/if}

		{#if hasCredentials && hasOAuth}
			<FieldSeparator>Or continue with</FieldSeparator>
		{/if}

		{#if !hasCredentials && hasOAuth}
			<div class="flex flex-col items-center gap-1 text-center">
				<h1 class="text-2xl font-bold">Login to your account</h1>
			</div>
		{/if}

		{#each oauthProviders as p (p.id)}
			{@const Icon = iconFor(p.icon)}
			<Field>
				<Button variant="outline" type="button" onclick={() => startOAuth(p)} disabled={loading}>
					{#if p.icon === 'github'}
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="size-4">
							<path
								d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"
								fill="currentColor"
							/>
						</svg>
					{:else}
						<Icon class="size-4" />
					{/if}
					{loading ? 'Redirecting...' : `Login with ${p.name}`}
				</Button>
			</Field>
		{/each}

		<p class="text-center text-sm text-muted-foreground">
			Don't have an account?
			<a
				href="#"
				onclick={handleSignUp}
				class="underline underline-offset-4"
			>
				Sign up
			</a>
		</p>
	</FieldGroup>
</form>
