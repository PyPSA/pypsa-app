import type {
	User,
	Network,
	NetworkShareResponse,
	Run,
	RunSummary,
	Backend,
	BackendPublic,
	TaskStatus,
	PlotResponse,
	PlotData,
	VersionInfo,
	HealthStatus,
	ApiError,
	ApiKey,
	NetworkFilters,
	NetworkUpdate,
	OutputFile,
	Visibility,
	PaginatedResponse,
	Workflow,
	ComponentListResponse,
	ComponentDataResponse,
	ComponentTimeseriesResponse,
	SavedView,
	SavedViewListResponse,
	ViewConfig,
	MapDataResponse,
} from "$lib/types.js";

const API_BASE = '/api/v1';

// Track active requests to enable cancellation
const activeControllers = new Map<string, AbortController>();

async function request<T>(endpoint: string, options: RequestInit = {}, cancellationKey: string | null = null): Promise<T> {
	const url = `${API_BASE}${endpoint}`;

	// Handle request cancellation
	const controller = new AbortController();
	if (cancellationKey) {
		// Cancel any previous request with the same key
		if (activeControllers.has(cancellationKey)) {
			activeControllers.get(cancellationKey)!.abort();
		}
		activeControllers.set(cancellationKey, controller);
	}

	const { headers: optHeaders, ...restOptions } = options;
	const headers: Record<string, string> = options.body instanceof FormData
		? { ...(optHeaders as Record<string, string>) }
		: { 'Content-Type': 'application/json', ...(optHeaders as Record<string, string>) };

	const config: RequestInit = {
		...restOptions,
		headers,
		credentials: 'include',
		signal: controller.signal,
	};

	try {
		const response = await fetch(url, config);

		if (!response.ok) {
			const error = await response.json().catch(() => ({ detail: response.statusText }));
			const err: ApiError = new Error(error.detail || `HTTP ${response.status}: ${response.statusText}`);
			err.status = response.status;

			// 401 = auth required, redirect to login (skip for auth endpoints themselves)
			if (response.status === 401 && !endpoint.includes('/auth/')) {
				if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
					window.location.href = '/login';
				}
			}

			throw err;
		}

		if (response.status === 204) {
			return undefined as T;
		}
		return await response.json();
	} catch (error) {
		if (error instanceof Error && error.name === 'AbortError') {
			const cancelError: ApiError = new Error('Request cancelled');
			cancelError.cancelled = true;
			throw cancelError;
		}
		console.error('API request failed:', error);
		throw error;
	} finally {
		// Clean up the controller
		if (cancellationKey && activeControllers.get(cancellationKey) === controller) {
			activeControllers.delete(cancellationKey);
		}
	}
}

// Auth API
export const auth = {
	async me(): Promise<User> {
		return request<User>('/auth/me');
	},
	logout(): void {
		window.location.href = '/api/v1/auth/logout';
	},
	login(): void {
		window.location.href = '/api/v1/auth/login';
	}
};

// Networks API
export const networks = {
	async list(skip = 0, limit = 100, owners: string[] | null = null): Promise<PaginatedResponse<Network>> {
		const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
		if (owners && owners.length > 0) {
			owners.forEach(owner => params.append('owners', owner));
		}
		return request<PaginatedResponse<Network>>(`/networks/?${params}`);
	},
	async get(id: string): Promise<Network> {
		return request<Network>(`/networks/${id}`, {}, `network-${id}`);
	},
	async getSummary(id: string): Promise<Record<string, unknown>> {
		return request<Record<string, unknown>>(`/networks/${id}/summary`, {}, `network-summary-${id}`);
	},
	async upload(file: File): Promise<Network> {
		const formData = new FormData();
		formData.append('file', file);
		return request<Network>('/networks/', { method: 'POST', body: formData });
	},
	async reset(): Promise<void> {
		return request<void>('/networks/reset', { method: 'DELETE' });
	},
	async delete(id: string): Promise<void> {
		return request<void>(`/networks/${id}`, { method: 'DELETE' });
	},
	async searchUsers(q: string): Promise<{ id: string; username: string; avatar_url?: string }[]> {
		return request<{ id: string; username: string; avatar_url?: string }[]>(
			`/networks/users/search?q=${encodeURIComponent(q)}`
		);
	},
	async getShares(id: string): Promise<NetworkShareResponse> {
		return request<NetworkShareResponse>(`/networks/${id}/shares`);
	},
	async shareWith(id: string, userId: string): Promise<NetworkShareResponse> {
		return request<NetworkShareResponse>(`/networks/${id}/shares`, {
			method: 'POST',
			body: JSON.stringify({ user_id: userId })
		});
	},
	async unshare(id: string, userId: string): Promise<NetworkShareResponse> {
		return request<NetworkShareResponse>(`/networks/${id}/shares/${userId}`, { method: 'DELETE' });
	},
	async updateVisibility(id: string, visibility: Visibility): Promise<Network> {
		return request<Network>(`/networks/${id}`, {
			method: 'PATCH',
			body: JSON.stringify({ visibility })
		});
	},
	async getComponents(id: string): Promise<ComponentListResponse> {
		return request<ComponentListResponse>(`/networks/${id}/components`, {}, `components-${id}`);
	},
	async getComponentData(
		id: string,
		componentName: string,
		params: { skip?: number; limit?: number; sort_by?: string; sort_desc?: boolean; search?: string } = {}
	): Promise<ComponentDataResponse> {
		const searchParams = new URLSearchParams();
		if (params.skip !== undefined) searchParams.set('skip', String(params.skip));
		if (params.limit !== undefined) searchParams.set('limit', String(params.limit));
		if (params.sort_by) searchParams.set('sort_by', params.sort_by);
		if (params.sort_desc) searchParams.set('sort_desc', 'true');
		if (params.search) searchParams.set('search', params.search);
		const qs = searchParams.toString();
		return request<ComponentDataResponse>(
			`/networks/${id}/components/${componentName}${qs ? '?' + qs : ''}`,
			{},
			`component-data-${id}-${componentName}`
		);
	},
	async getComponentTimeseries(
		id: string,
		componentName: string,
		attr: string,
		params: { skip?: number; limit?: number } = {}
	): Promise<ComponentTimeseriesResponse> {
		const searchParams = new URLSearchParams();
		if (params.skip !== undefined) searchParams.set('skip', String(params.skip));
		if (params.limit !== undefined) searchParams.set('limit', String(params.limit));
		const qs = searchParams.toString();
		return request<ComponentTimeseriesResponse>(
			`/networks/${id}/components/${componentName}/timeseries/${attr}${qs ? '?' + qs : ''}`,
			{},
			`component-ts-${id}-${componentName}-${attr}`
		);
	},
	async getMapData(id: string, carriers?: string[]): Promise<MapDataResponse> {
		const params = new URLSearchParams();
		if (carriers && carriers.length > 0) {
			carriers.forEach(c => params.append('carriers', c));
		}
		const qs = params.toString();
		return request<MapDataResponse>(
			`/networks/${id}/map${qs ? '?' + qs : ''}`,
			{},
			`map-${id}`
		);
	},
	async updateComponentData(
		id: string,
		componentName: string,
		updates: Record<string, Record<string, unknown>>
	): Promise<{ message: string }> {
		return request<{ message: string }>(`/networks/${id}/components/${componentName}`, {
			method: 'PATCH',
			body: JSON.stringify({ updates })
		});
	}
};

// Statistics API
export const statistics = {
	async get(networkIds: string | string[], statistic: string, parameters: Record<string, unknown> = {}): Promise<Record<string, unknown>> {
		// Ensure networkIds is always an array
		const idsArray = Array.isArray(networkIds) ? networkIds : [networkIds];
		const cacheKey = idsArray.length === 1 ? idsArray[0] : idsArray.sort().join(',');

		return request<Record<string, unknown>>('/statistics/', {
			method: 'POST',
			body: JSON.stringify({
				network_ids: idsArray,
				statistic,
				parameters
			})
		}, `statistics-${cacheKey}-${statistic}`);
	}
};

// Plots API
export const plots = {
	async generate(networkIds: string | string[], statistic: string, plotType: string, parameters: Record<string, unknown> = {}): Promise<PlotResponse> {
		// Ensure networkIds is always an array
		const idsArray = Array.isArray(networkIds) ? networkIds : [networkIds];
		const cacheKey = idsArray.length === 1 ? idsArray[0] : idsArray.sort().join(',');

		// Include parameters in cancellation key to ensure unique requests are properly cancelled
		const paramsKey = JSON.stringify(parameters);

		const response = await request<{ task_id?: string; plot_data?: PlotData; cached?: boolean; generated_at?: string; statistic?: string; plot_type?: string }>('/plots/generate', {
			method: 'POST',
			body: JSON.stringify({
				network_ids: idsArray,
				statistic,
				plot_type: plotType,
				parameters
			})
		}, `plot-${cacheKey}-${statistic}-${plotType}-${paramsKey}`);

		// Check if response is cached (synchronous) or async (task-based)
		if (response.task_id) {
			// Async response - poll for results
			return await this.pollTaskStatus(response.task_id);
		} else {
			// Cached response - return immediately
			return response as PlotResponse;
		}
	},

	async getStatus(taskId: string): Promise<TaskStatus> {
		return request<TaskStatus>(`/tasks/status/${taskId}`);
	},

	/** Poll task status until completion with exponential backoff */
	async pollTaskStatus(taskId: string, maxAttempts = 30): Promise<PlotResponse> {
		let attempts = 0;
		let delay = 200; // Start with 200ms

		while (attempts < maxAttempts) {
			await new Promise(resolve => setTimeout(resolve, delay));

			const status = await this.getStatus(taskId);

			if (status.state === 'SUCCESS' && status.result) {
				// Check if the result contains an error (task succeeded but operation failed)
				if (status.result.status === 'error') {
					// Create detailed error message
					let errorMessage = status.result.error || 'Plot generation failed';

					// Include error details if available (stack trace + parameters)
					if (status.result.error_details) {
						const details = status.result.error_details;
						errorMessage += '\n\nParameters:\n' + JSON.stringify(details.parameters, null, 2);

						if (details.stack_trace) {
							errorMessage += '\n\nStack Trace:\n' + details.stack_trace;
						}
					}

					throw new Error(errorMessage);
				}

				return {
					plot_data: status.result.data!,
					cached: false,
					generated_at: status.result.generated_at,
					statistic: status.result.request?.statistic,
					plot_type: status.result.request?.plot_type
				};
			} else if (status.state === 'FAILURE') {
				throw new Error(status.error || 'Plot generation failed');
			}

			// Exponential backoff with max 2 seconds
			delay = Math.min(delay * 1.5, 2000);
			attempts++;
		}

		throw new Error('Plot generation timed out');
	}

};

// Runs API
export const runs = {
	async list(
		skip = 0,
		limit = 100,
		filters?: { statuses?: string[]; workflows?: string[]; owners?: string[]; git_refs?: string[]; configfiles?: string[]; backends?: string[] }
	): Promise<PaginatedResponse<RunSummary>> {
		const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
		if (filters) {
			for (const [key, values] of Object.entries(filters)) {
				values?.forEach((v: string) => params.append(key, v));
			}
		}
		return request<PaginatedResponse<RunSummary>>(`/runs/?${params}`);
	},
	async get(id: string): Promise<Run> {
		return request<Run>(`/runs/${id}`, {}, `run-${id}`);
	},
	async cancel(id: string): Promise<void> {
		return request<void>(`/runs/${id}/cancel`, { method: 'POST' });
	},
	async backends(): Promise<BackendPublic[]> {
		return request<BackendPublic[]>('/runs/backends');
	},
	async create(body: { workflow: string; configfile?: string; snakemake_args?: string[]; extra_files?: Record<string, string>; cache?: { key: string; dirs: string[] }; import_networks?: string[]; backend_id?: string }): Promise<Run> {
		return request<Run>('/runs/', { method: 'POST', body: JSON.stringify(body) });
	},
	async rerun(run: Run): Promise<Run> {
		return this.create({
			workflow: run.workflow,
			configfile: run.configfile ?? undefined,
			snakemake_args: run.snakemake_args ?? undefined,
			extra_files: run.extra_files ?? undefined,
			cache: run.cache ?? undefined,
			import_networks: run.import_networks ?? undefined,
			backend_id: run.backend.id
		});
	},
	async remove(id: string): Promise<void> {
		return request<void>(`/runs/${id}`, { method: 'DELETE' });
	},
	async updateVisibility(id: string, visibility: Visibility): Promise<RunSummary> {
		return request<RunSummary>(`/runs/${id}`, {
			method: 'PATCH',
			body: JSON.stringify({ visibility })
		});
	},
	logsUrl(id: string): string {
		return `${API_BASE}/runs/${id}/logs`;
	},
	async listOutputs(id: string): Promise<OutputFile[]> {
		return request<OutputFile[]>(`/runs/${id}/outputs`);
	},
	outputDownloadUrl(id: string, path: string): string {
		const encoded = path.split('/').map(encodeURIComponent).join('/');
		return `${API_BASE}/runs/${id}/outputs/${encoded}`;
	},
	async workflow(id: string): Promise<Workflow> {
		return request<Workflow>(`/runs/${id}/workflow`, {}, `run-workflow-${id}`);
	}
};

// Views API
export const savedViews = {
	async list(networkId?: string, skip = 0, limit = 50): Promise<SavedViewListResponse> {
		const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
		if (networkId) params.set('network_id', networkId);
		return request<SavedViewListResponse>(`/views/?${params}`);
	},
	async get(id: string): Promise<SavedView> {
		return request<SavedView>(`/views/${id}`);
	},
	async create(body: {
		name: string;
		description?: string;
		network_id?: string;
		visibility?: string;
		config: ViewConfig;
	}): Promise<SavedView> {
		return request<SavedView>('/views/', { method: 'POST', body: JSON.stringify(body) });
	},
	async update(id: string, body: {
		name?: string;
		description?: string;
		visibility?: string;
		config?: ViewConfig;
	}): Promise<SavedView> {
		return request<SavedView>(`/views/${id}`, { method: 'PATCH', body: JSON.stringify(body) });
	},
	async delete(id: string): Promise<void> {
		return request<void>(`/views/${id}`, { method: 'DELETE' });
	}
};

// Cache API
export const cache = {
	async clearNetwork(networkId: string): Promise<void> {
		return request<void>(`/cache/${networkId}`, { method: 'DELETE' });
	},
	async clearAll(): Promise<void> {
		return request<void>('/cache/', { method: 'DELETE' });
	}
};

// Version API
export const version = {
	async get(): Promise<VersionInfo> {
		return request<VersionInfo>('/version/');
	}
};

// Health check
export const health = {
	async check(): Promise<HealthStatus> {
		// Health endpoint is outside /api/v1
		const url = '/health';
		const response = await fetch(url);
		if (!response.ok) {
			throw new Error(`HTTP ${response.status}: ${response.statusText}`);
		}
		return await response.json();
	}
};

// Admin API
export const admin = {
	async listUsers(skip = 0, limit = 100, role: string | null = null): Promise<PaginatedResponse<User>> {
		let url = `/admin/users?skip=${skip}&limit=${limit}`;
		if (role) url += `&role=${role}`;
		return request<PaginatedResponse<User>>(url);
	},

	async approveUser(userId: string): Promise<User> {
		return request<User>(`/admin/users/${userId}/approve`, { method: 'POST' });
	},

	async updateUserRole(userId: string, role: string): Promise<User> {
		return request<User>(`/admin/users/${userId}/role`, {
			method: 'PATCH',
			body: JSON.stringify({ role })
		});
	},

	async createUser(username: string, role: string = 'bot', avatarUrl?: string): Promise<User> {
		return request<User>('/admin/users', {
			method: 'POST',
			body: JSON.stringify({ username, role, avatar_url: avatarUrl || null })
		});
	},

	async deleteUser(userId: string): Promise<void> {
		return request<void>(`/admin/users/${userId}`, { method: 'DELETE' });
	},

	async listNetworks(skip = 0, limit = 100, filters: NetworkFilters = {}): Promise<PaginatedResponse<Network>> {
		let url = `/admin/networks?skip=${skip}&limit=${limit}`;
		if (filters.visibility) url += `&visibility=${filters.visibility}`;
		if (filters.owner) url += `&owner=${filters.owner}`;
		return request<PaginatedResponse<Network>>(url);
	},

	async updateNetwork(networkId: string, updates: NetworkUpdate): Promise<Network> {
		return request<Network>(`/admin/networks/${networkId}`, {
			method: 'PATCH',
			body: JSON.stringify(updates)
		});
	},

	async deleteNetwork(networkId: string): Promise<void> {
		return request<void>(`/admin/networks/${networkId}`, { method: 'DELETE' });
	},

	async listRuns(skip = 0, limit = 100, filters: { visibility?: string; owner?: string } = {}): Promise<PaginatedResponse<RunSummary>> {
		let url = `/admin/runs?skip=${skip}&limit=${limit}`;
		if (filters.visibility) url += `&visibility=${filters.visibility}`;
		if (filters.owner) url += `&owner=${filters.owner}`;
		return request<PaginatedResponse<RunSummary>>(url);
	},

	async updateRun(runId: string, updates: { visibility?: Visibility; user_id?: string }): Promise<Run> {
		return request<Run>(`/admin/runs/${runId}`, {
			method: 'PATCH',
			body: JSON.stringify(updates)
		});
	},

	async deleteRun(runId: string): Promise<void> {
		return request<void>(`/admin/runs/${runId}`, { method: 'DELETE' });
	},

	async getPermissions(): Promise<Record<string, unknown>> {
		return request<Record<string, unknown>>('/admin/permissions');
	},

	async listBackends(): Promise<Backend[]> {
		return request<Backend[]>('/admin/backends');
	},

	async listBackendUsers(backendId: string): Promise<User[]> {
		return request<User[]>(`/admin/backends/${backendId}/users`);
	},

	async assignUserToBackend(backendId: string, userId: string): Promise<void> {
		return request<void>(`/admin/backends/${backendId}/users`, {
			method: 'POST',
			body: JSON.stringify({ user_id: userId })
		});
	},

	async unassignUserFromBackend(backendId: string, userId: string): Promise<void> {
		return request<void>(`/admin/backends/${backendId}/users/${userId}`, { method: 'DELETE' });
	}
};

// API Keys
export const apiKeys = {
	async list(): Promise<ApiKey[]> {
		return request<ApiKey[]>('/auth/api-keys/');
	},

	async create(name: string, expiresInDays: number, userId: string): Promise<ApiKey> {
		return request<ApiKey>('/auth/api-keys/', {
			method: 'POST',
			body: JSON.stringify({ name, expires_in_days: expiresInDays, user_id: userId })
		});
	},

	async delete(keyId: string): Promise<void> {
		return request<void>(`/auth/api-keys/${keyId}`, { method: 'DELETE' });
	}
};
