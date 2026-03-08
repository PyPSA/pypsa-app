// API response types
//

export interface User {
	id: string;
	username: string;
	email?: string;
	avatar_url?: string;
	permissions: string[];
	role: string;
	created_at?: string;
	last_login?: string;
}

export interface ApiKey {
	id: string;
	name: string;
	key_prefix: string;
	user_id: string;
	created_at: string;
	last_used_at?: string;
	expires_at?: string;
	key?: string;
}

export interface NetworkTag {
	name: string;
	url?: string;
}

export interface Carrier {
	name: string;
	nice_name?: string;
}

export interface Network {
	id: string;
	name?: string;
	filename: string;
	file_path: string;
	file_size?: number;
	visibility: "public" | "private";
	owner: User;
	source_run_id?: string;
	dimensions?: Record<string, number>;
	dimensions_count?: number;
	components?: Record<string, number>;
	components_count?: number;
	tags?: (string | NetworkTag)[];
	update_history?: string[];
	created_at?: string;
	updated_at?: string;
}

export type RunStatus = "PENDING" | "SETUP" | "RUNNING" | "UPLOADING" | "COMPLETED" | "FAILED" | "ERROR" | "CANCELLED";

/** Statuses where the run will not change further (no polling needed). */
export const RUN_FINAL_STATUSES: ReadonlySet<RunStatus> = new Set(["COMPLETED", "FAILED", "ERROR", "CANCELLED"]);

/** Statuses where user actions (cancel, remove) are no longer available. */
export const RUN_SETTLED_STATUSES: ReadonlySet<RunStatus> = new Set(["UPLOADING", "COMPLETED", "FAILED", "ERROR", "CANCELLED"]);

export interface Run {
	id: string;
	status: RunStatus;
	workflow: string;
	configfile?: string;
	snakemake_args?: string[];
	extra_files?: Record<string, string>;
	cache?: { key: string; dirs: string[] };
	import_networks?: string[];
	git_ref?: string;
	git_sha?: string;
	exit_code?: number | null;
	started_at?: string;
	completed_at?: string;
	created_at: string;
	owner: User;
}

export interface TaskStatus {
	task_id: string;
	state: "PENDING" | "STARTED" | "SUCCESS" | "FAILURE";
	result?: TaskResult;
	error?: string;
}

export interface TaskResult {
	status?: "success" | "error";
	data?: PlotData;
	error?: string;
	error_details?: {
		parameters?: Record<string, unknown>;
		stack_trace?: string;
	};
	generated_at?: string;
	request?: {
		statistic?: string;
		plot_type?: string;
	};
}

export interface OutputFile {
	path: string;
	size: number;
}

export type PlotData = Record<string, unknown>;

export interface PlotResponse {
	plot_data: PlotData;
	cached: boolean;
	generated_at?: string;
	statistic?: string;
	plot_type?: string;
}

export interface StatisticsRequest {
	network_ids: string[];
	statistic: string;
	parameters: Record<string, unknown>;
}

export interface PlotRequest {
	network_ids: string[];
	statistic: string;
	plot_type: string;
	parameters: Record<string, unknown>;
}

export interface VersionInfo {
	version: string;
	[key: string]: unknown;
}

export interface HealthStatus {
	status: string;
	[key: string]: unknown;
}

export interface NetworkFilters {
	visibility?: string;
	owner?: string;
}

export interface NetworkUpdate {
	visibility?: "public" | "private";
	[key: string]: unknown;
}

// Paginated response type

export interface PaginatedResponse<T> {
	data: T[];
	meta: {
		total: number;
		skip: number;
		limit: number;
		owners?: User[];
	};
}

// Store types

export interface AuthState {
	user: User | null;
	loading: boolean;
	error: string | null;
	authEnabled: boolean | null;
}

// Shared utility types

export type TagType = "default" | "config" | "version" | "model";
export type TagColor = "tag-model" | "tag-version" | "tag-config" | "tag-default";
export type Permission = string;

// API error type

export interface ApiError extends Error {
	status?: number;
	cancelled?: boolean;
}
