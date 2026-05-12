import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		proxy: {
			'/api': {
				target: 'http://localhost:8000',
				changeOrigin: true
			}
		}
	},
	ssr: {
		noExternal: ['bits-ui', 'mode-watcher', '@deck.gl/core', '@deck.gl/layers', '@deck.gl/carto', 'maplibre-gl']
	}
});
