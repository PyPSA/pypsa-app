<script lang="ts">
	import type { WorkflowRule, Rulegraph } from '$lib/types.js';
	import ELK from 'elkjs/lib/elk.bundled.js';

	let {
		rulegraph,
		rules,
		onSelectRule
	}: {
		rulegraph: Rulegraph;
		rules: WorkflowRule[];
		onSelectRule: (name: string) => void;
	} = $props();

	interface LayoutNode { id: string; x: number; y: number; width: number; height: number }
	interface LayoutEdge { id: string; sections: { startPoint: { x: number; y: number }; endPoint: { x: number; y: number }; bendPoints?: { x: number; y: number }[] }[] }

	let layoutNodes = $state<LayoutNode[]>([]);
	let layoutEdges = $state<LayoutEdge[]>([]);
	let graphWidth = $state(0);
	let graphHeight = $state(0);

	const NODE_W = 160;
	const NODE_H = 40;
	const PADDING = 20;

	const ruleMap = $derived(new Map(rules.map(r => [r.name, r])));

	function nodeColor(name: string): string {
		const rule = ruleMap.get(name);
		if (!rule) return '#6b7280'; // gray
		if (rule.jobs_finished >= rule.total_job_count && rule.total_job_count > 0) return '#098754'; // primary
		if (rule.jobs_finished > 0) return '#eab308'; // yellow
		return '#6b7280'; // gray
	}

	function nodeLabel(name: string): string {
		const rule = ruleMap.get(name);
		if (!rule) return name;
		return `${name} (${rule.jobs_finished}/${rule.total_job_count})`;
	}

	// Cache the node set to only re-layout when the graph structure changes
	let lastNodeKey = '';
	const elk = new ELK();

	$effect(() => {
		const nodeKey = rulegraph.nodes.map(n => n.rule).join(',') + '|' + rulegraph.links.map(l => `${l.sourcerule}-${l.targetrule}`).join(',');
		if (nodeKey === lastNodeKey) return;
		lastNodeKey = nodeKey;

		const graph = {
			id: 'root',
			layoutOptions: {
				'elk.algorithm': 'layered',
				'elk.direction': 'RIGHT',
				'elk.spacing.nodeNode': '30',
				'elk.layered.spacing.nodeNodeBetweenLayers': '50',
			},
			children: rulegraph.nodes.map(n => ({
				id: n.rule,
				width: NODE_W,
				height: NODE_H,
			})),
			edges: rulegraph.links.map((l, i) => ({
				id: `e${i}`,
				sources: [l.sourcerule],
				targets: [l.targetrule],
			})),
		};

		elk.layout(graph).then(layout => {
			layoutNodes = (layout.children ?? []).map(n => ({
				id: n.id,
				x: (n.x ?? 0) + PADDING,
				y: (n.y ?? 0) + PADDING,
				width: n.width ?? NODE_W,
				height: n.height ?? NODE_H,
			}));
			layoutEdges = ((layout.edges ?? []) as unknown as LayoutEdge[]).map(e => ({
				id: e.id,
				sections: e.sections,
			}));
			graphWidth = ((layout as unknown as { width: number }).width ?? 400) + PADDING * 2;
			graphHeight = ((layout as unknown as { height: number }).height ?? 200) + PADDING * 2;
		});
	});

	function edgePath(edge: LayoutEdge): string {
		if (!edge.sections || edge.sections.length === 0) return '';
		const s = edge.sections[0];
		let d = `M ${s.startPoint.x + PADDING} ${s.startPoint.y + PADDING}`;
		if (s.bendPoints) {
			for (const bp of s.bendPoints) {
				d += ` L ${bp.x + PADDING} ${bp.y + PADDING}`;
			}
		}
		d += ` L ${s.endPoint.x + PADDING} ${s.endPoint.y + PADDING}`;
		return d;
	}
</script>

{#if layoutNodes.length > 0}
	<div class="overflow-x-auto">
		<svg width={graphWidth} height={graphHeight} class="block">
			<defs>
				<marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
					<polygon points="0 0, 8 3, 0 6" fill="#6b7280" />
				</marker>
			</defs>

			{#each layoutEdges as edge}
				<path
					d={edgePath(edge)}
					fill="none"
					stroke="#6b7280"
					stroke-width="1.5"
					marker-end="url(#arrowhead)"
				/>
			{/each}

			{#each layoutNodes as node}
				<g
					class="cursor-pointer"
					onclick={() => onSelectRule(node.id)}
					role="button"
					tabindex="0"
					onkeydown={(e) => { if (e.key === 'Enter') onSelectRule(node.id); }}
				>
					<rect
						x={node.x}
						y={node.y}
						width={node.width}
						height={node.height}
						rx="6"
						fill={nodeColor(node.id)}
						opacity="0.15"
						stroke={nodeColor(node.id)}
						stroke-width="2"
					/>
					<text
						x={node.x + node.width / 2}
						y={node.y + node.height / 2}
						text-anchor="middle"
						dominant-baseline="central"
						class="text-[11px] fill-foreground font-medium pointer-events-none"
					>
						{nodeLabel(node.id)}
					</text>
				</g>
			{/each}
		</svg>
	</div>
{/if}
