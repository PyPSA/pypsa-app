<script lang="ts">
	import { page } from '$app/stores';
</script>

<div class="min-h-screen flex flex-col items-center justify-center text-center">
	<h1 class="text-4xl font-bold mb-2">{$page.status}</h1>
	<p class="text-sm text-muted-foreground">{$page.error?.message ?? 'Something went wrong'}</p>
</div>
