/**
 * API client for PyPSA backend
 *
 * During development, Vite will proxy /api requests to the backend
 */

const API_BASE = '/api/v1';

// Track active requests to enable cancellation
const activeControllers = new Map();

/**
 * Make a request to the API
 * @param {string} endpoint - API endpoint (e.g., '/networks')
 * @param {RequestInit} options - Fetch options
 * @param {string} cancellationKey - Optional key for request cancellation
 * @returns {Promise<any>}
 */
async function request(endpoint, options = {}, cancellationKey = null) {
	const url = `${API_BASE}${endpoint}`;

	// Handle request cancellation
	const controller = new AbortController();
	if (cancellationKey) {
		// Cancel any previous request with the same key
		if (activeControllers.has(cancellationKey)) {
			activeControllers.get(cancellationKey).abort();
		}
		activeControllers.set(cancellationKey, controller);
	}

	const config = {
		headers: {
			'Content-Type': 'application/json',
			...options.headers,
		},
		credentials: 'include', // Include cookies for authentication
		signal: controller.signal,
		...options,
	};

	try {
		const response = await fetch(url, config);

		if (!response.ok) {
			const error = await response.json().catch(() => ({ detail: response.statusText }));
			const err = new Error(error.detail || `HTTP ${response.status}: ${response.statusText}`);
			err.status = response.status;

			// Handle authentication errors - but only redirect for 401, not 400
			// 400 means auth is disabled, 401 means auth is enabled but user not logged in
			if (response.status === 401 && !endpoint.includes('/auth/')) {
				// Redirect to login page if not authenticated (except for auth endpoints)
				if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
					window.location.href = '/login';
				}
			}

			throw err;
		}

		return await response.json();
	} catch (error) {
		// Don't log AbortError as it's expected when cancelling requests
		if (error.name === 'AbortError') {
			console.log('Request cancelled:', endpoint);
			return null;
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
	async me() {
		return request('/auth/me');
	},
	logout() {
		window.location.href = '/api/v1/auth/logout';
	},
	login() {
		window.location.href = '/api/v1/auth/login';
	}
};

// Networks API
export const networks = {
	async list(skip = 0, limit = 100) {
		return request(`/networks/?skip=${skip}&limit=${limit}`);
	},
	async get(id) {
		return request(`/networks/${id}`, {}, `network-${id}`);
	},
	async getSummary(id) {
		return request(`/networks/${id}/summary`, {}, `network-summary-${id}`);
	},
	async scan() {
		return request('/networks/', { method: 'PUT' });
	},
	async getScanStatus(taskId) {
		return request(`/tasks/status/${taskId}`);
	},
	async reset() {
		return request('/networks/reset', { method: 'DELETE' });
	},
	async delete(id) {
		return request(`/networks/${id}`, { method: 'DELETE' });
	}
};

// Statistics API
export const statistics = {
	async get(networkIds, statistic, parameters = {}) {
		// Ensure networkIds is always an array
		const idsArray = Array.isArray(networkIds) ? networkIds : [networkIds];
		const cacheKey = idsArray.length === 1 ? idsArray[0] : idsArray.sort().join(',');

		return request('/statistics/', {
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
	async generate(networkIds, statistic, plotType, parameters = {}) {
		// Ensure networkIds is always an array
		const idsArray = Array.isArray(networkIds) ? networkIds : [networkIds];
		const cacheKey = idsArray.length === 1 ? idsArray[0] : idsArray.sort().join(',');

		// Include parameters in cancellation key to ensure unique requests are properly cancelled
		const paramsKey = JSON.stringify(parameters);

		const response = await request('/plots/generate', {
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
			return response;
		}
	},

	async getStatus(taskId) {
		return request(`/tasks/status/${taskId}`);
	},

	/** Poll task status until completion with exponential backoff */
	async pollTaskStatus(taskId, maxAttempts = 30) {
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
					plot_data: status.result.data,
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

// Cache API
export const cache = {
	async clearNetwork(networkId) {
		return request(`/cache/${networkId}`, { method: 'DELETE' });
	},
	async clearAll() {
		return request('/cache/', { method: 'DELETE' });
	}
};

// Version API
export const version = {
	async get() {
		return request('/version/');
	}
};

// Health check
export const health = {
	async check() {
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
	/** List users with optional role filter */
	async listUsers(skip = 0, limit = 100, role = null) {
		let url = `/admin/users?skip=${skip}&limit=${limit}`;
		if (role) url += `&role=${role}`;
		return request(url);
	},

	/** Approve a pending user */
	async approveUser(userId) {
		return request(`/admin/users/${userId}/approve`, { method: 'POST' });
	},

	/** Update user role */
	async updateUserRole(userId, role) {
		return request(`/admin/users/${userId}/role`, {
			method: 'PATCH',
			body: JSON.stringify({ role })
		});
	},

	/** Delete a user */
	async deleteUser(userId) {
		return request(`/admin/users/${userId}`, { method: 'DELETE' });
	}
};
