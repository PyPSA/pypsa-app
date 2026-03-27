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
	owner: User;
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
	visibility: Visibility;
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

export type Visibility = "public" | "private";

export interface BackendPublic {
	id: string;
	name: string;
	is_active: boolean;
}

export interface Backend extends BackendPublic {
	url: string;
	created_at: string;
	updated_at?: string;
}

export type RunStatus = "PENDING" | "SETUP" | "RUNNING" | "UPLOADING" | "COMPLETED" | "FAILED" | "ERROR" | "CANCELLED";

/** Statuses where the run will not change further (no polling needed). */
export const RUN_FINAL_STATUSES: ReadonlySet<RunStatus> = new Set(["COMPLETED", "FAILED", "ERROR", "CANCELLED"]);

/** Statuses where user actions (cancel, remove) are no longer available. */
export const RUN_SETTLED_STATUSES: ReadonlySet<RunStatus> = new Set(["UPLOADING", "COMPLETED", "FAILED", "ERROR", "CANCELLED"]);

export interface RunNetwork {
	id: string;
	name: string | null;
	filename: string;
}

export interface UserPublic {
	id: string;
	username: string;
	avatar_url?: string;
}

export interface RunSummary {
	id: string;
	status: RunStatus;
	workflow: string;
	configfile?: string;
	git_ref?: string;
	git_sha?: string;
	started_at?: string;
	completed_at?: string;
	created_at: string;
	owner: UserPublic;
	visibility: Visibility;
	backend: BackendPublic;
	total_job_count?: number;
	jobs_finished?: number;
}

export interface Run extends RunSummary {
	snakemake_args?: string[];
	extra_files?: Record<string, string>;
	cache?: { key: string; dirs: string[] };
	import_networks?: string[];

	networks: RunNetwork[];
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
	visibility?: Visibility;
	user_id?: string;
}

// Paginated response type

export interface PaginatedResponse<T> {
	data: T[];
	meta: {
		total: number;
		skip: number;
		limit: number;
		owners?: User[];
		statuses?: string[];
		workflows?: string[];
		git_refs?: string[];
		configfiles?: string[];
		backends?: BackendPublic[];
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

// Workflow types

export interface WorkflowFile {
	path: string;
	file_type: string;
}

export interface WorkflowJob {
	snakemake_id: number;
	rule: string;
	status: string;
	wildcards: Record<string, string> | null;
	threads: number;
	started_at?: string;
	completed_at?: string;
	files: WorkflowFile[];
	log?: string;
}

export interface WorkflowRule {
	name: string;
	total_job_count: number;
	jobs_finished: number;
	jobs: WorkflowJob[];
}

export interface WorkflowError {
	timestamp: string;
	exception: string;
	rule: string | null;
	traceback: string | null;
}

export interface RulegraphNode {
	rule: string;
}

export interface RulegraphLink {
	source: number;
	target: number;
	sourcerule: string;
	targetrule: string;
}

export interface Rulegraph {
	nodes: RulegraphNode[];
	links: RulegraphLink[];
}

export interface Workflow {
	workflow_id: string;
	status: string;
	total_job_count: number;
	jobs_finished: number;
	rulegraph: Rulegraph | null;
	rules: WorkflowRule[];
	errors: WorkflowError[];
}

// API error type

export interface ApiError extends Error {
	status?: number;
	cancelled?: boolean;
}

// Public (unauthenticated) response types

export interface PublicRunResponse {
	id: string;
	status: RunStatus;
	workflow: string;
	configfile?: string;
	git_ref?: string;
	git_sha?: string;
	created_at: string;
	started_at?: string;
	completed_at?: string;

	total_job_count?: number;
	jobs_finished?: number;
	visibility: Visibility;
	owner: UserPublic;
	backend: BackendPublic;
	networks: RunNetwork[];
}
