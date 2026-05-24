<script>
  import { onMount, onDestroy } from 'svelte';
  import { EventsOn, EventsOff } from '../wailsjs/runtime/runtime.js';

  let phase = 'starting';
  let message = 'Initialising…';
  let pct = 0;
  let error = '';

  onMount(() => {
    EventsOn('status', (ev) => {
      phase = ev.phase;
      message = ev.message;
      pct = ev.pct;
      error = ev.err || '';
    });

    EventsOn('navigate', (url) => {
      window.location.href = url;
    });
  });

  onDestroy(() => {
    EventsOff('status', 'navigate');
  });

  function retry() {
    window.location.reload();
  }
</script>

<div class="shell">
  <div class="card">
    <div class="logo">
      <span class="name">pypsa</span><span class="accent">-app</span>
    </div>

    {#if error}
      <p class="error-msg">{error}</p>
      <button class="btn" on:click={retry}>Retry</button>
    {:else}
      <p class="status-text">{message}</p>
      <div class="progress-track">
        <div class="progress-fill" style="width: {pct}%"></div>
      </div>
      <span class="pct-label">{pct}%</span>
    {/if}
  </div>
</div>

<style>
  .shell {
    width: 100vw;
    height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #111827;
  }

  .card {
    width: 380px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 18px;
  }

  .logo {
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin-bottom: 4px;
  }
  .name  { color: #f9fafb; }
  .accent { color: #3b82f6; }

  .status-text {
    color: #9ca3af;
    font-size: 0.875rem;
    min-height: 20px;
    text-align: center;
  }

  .progress-track {
    width: 100%;
    height: 4px;
    background: #1f2937;
    border-radius: 2px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: #3b82f6;
    border-radius: 2px;
    transition: width 0.3s ease;
  }

  .pct-label {
    color: #4b5563;
    font-size: 0.75rem;
    font-variant-numeric: tabular-nums;
  }

  .error-msg {
    color: #f87171;
    font-size: 0.875rem;
    text-align: center;
    line-height: 1.6;
    padding: 0 8px;
  }

  .btn {
    padding: 8px 28px;
    background: #3b82f6;
    color: #fff;
    border: none;
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
  }
  .btn:hover { background: #2563eb; }
</style>
