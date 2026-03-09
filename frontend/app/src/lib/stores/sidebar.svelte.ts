let open = $state(true);

export const sidebarStore = {
	get open() {
		return open;
	},
	set open(value: boolean) {
		open = value;
	}
};
