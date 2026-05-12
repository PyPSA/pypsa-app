<script lang="ts">
	import SunIcon from "@lucide/svelte/icons/sun";
	import MoonIcon from "@lucide/svelte/icons/moon";

	import { toggleMode } from "mode-watcher";
	import { Button } from "$lib/components/ui/button/index.js";
</script>

<Button onclick={toggleMode} variant="ghost" size="icon-lg">
	<SunIcon class="dark:hidden" />
	<MoonIcon class="hidden dark:block" />
	<span class="sr-only">Toggle theme</span>
</Button>
