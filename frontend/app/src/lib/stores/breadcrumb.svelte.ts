let subItems = $state<{ label: string; href?: string }[]>([]);

export const breadcrumbStore = {
	get items() {
		return subItems;
	},
	set(items: { label: string; href?: string }[]) {
		subItems = items;
	},
	clear() {
		subItems = [];
	}
};
