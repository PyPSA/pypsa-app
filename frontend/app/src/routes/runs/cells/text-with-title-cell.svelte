<script lang="ts">
  let { text, title = '' }: { text: string; title: string } = $props();
</script>

<span {title}>{text}</span>
