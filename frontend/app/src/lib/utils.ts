import { browser } from '$app/environment';
import type { VisibilityState } from '@tanstack/table-core';
import { toast } from 'svelte-sonner';
import type { NetworkTag, TagType, TagColor, User } from "./types.js";
import type { FilterOption } from '$lib/components/ui/filter-dialog';

export { cn } from "$lib/lib/utils.js";

/**
 * Copy text to clipboard with success/error toast.
 */
export async function copyToClipboard(text: string): Promise<void> {
	try {
		await navigator.clipboard.writeText(text);
		toast.success('Copied to clipboard');
	} catch {
		toast.error('Failed to copy to clipboard');
	}
}

/**
 * Load persisted table preferences (pageSize, columnVisibility) from localStorage.
 */
export function loadTablePrefs(prefix: string): {
	pageSize: number | null;
	columnVisibility: VisibilityState | null;
} {
	if (!browser) return { pageSize: null, columnVisibility: null };
	const raw = localStorage.getItem(`${prefix}PageSize`);
	const pageSize = raw ? parseInt(raw) : null;
	let columnVisibility: VisibilityState | null = null;
	const savedVis = localStorage.getItem(`${prefix}ColumnVisibility`);
	if (savedVis) {
		try { columnVisibility = JSON.parse(savedVis); } catch { /* use default */ }
	}
	return { pageSize: isNaN(pageSize as number) ? null : pageSize, columnVisibility };
}

/**
 * Save a single table preference to localStorage.
 */
export function saveTablePref(prefix: string, key: 'pageSize' | 'columnVisibility', value: number | VisibilityState): void {
	if (!browser) return;
	const storageKey = `${prefix}${key === 'pageSize' ? 'PageSize' : 'ColumnVisibility'}`;
	localStorage.setItem(storageKey, typeof value === 'number' ? value.toString() : JSON.stringify(value));
}

/**
 * Correct page if it exceeds total pages; returns null if no change needed.
 */
export function clampPage(page: number, pageSize: number, total: number): number | null {
	const totalPages = Math.ceil(total / pageSize);
	if (page > totalPages && totalPages > 0) {
		return totalPages;
	}
	return null;
}

/**
 * Build owner filter options with the current user listed first.
 */
export function buildOwnerOptions(availableOwners: User[], currentUsername?: string): FilterOption[] {
	const opts: FilterOption[] = [];
	const currentUserInOwners = availableOwners.find(o => o.username === currentUsername);
	if (currentUserInOwners) {
		opts.push({ id: currentUserInOwners.username, label: currentUserInOwners.username, avatarUrl: currentUserInOwners.avatar_url });
	}
	for (const owner of availableOwners) {
		if (owner.username !== currentUsername) {
			opts.push({ id: owner.username, label: owner.username, avatarUrl: owner.avatar_url });
		}
	}
	return opts;
}

export function formatFileSize(bytes: number | null | undefined): string {
	if (bytes === null || bytes === undefined || bytes === 0) return '—';
	if (bytes < 1024) return `${bytes} B`;
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
	if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function parseUTCDate(dateString: string): Date {
	return new Date(dateString.endsWith('Z') ? dateString : dateString + 'Z');
}

export function formatDate(dateString: string | null | undefined): string {
	if (!dateString) return '—';
	const date = parseUTCDate(dateString);
	return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour12: false });
}

function formatSeconds(seconds: number): string {
	if (seconds < 60) return `${seconds}s`;
	const minutes = Math.floor(seconds / 60);
	const secs = seconds % 60;
	if (minutes < 60) return `${minutes}m ${secs}s`;
	const hours = Math.floor(minutes / 60);
	const mins = minutes % 60;
	if (hours >= 24) {
		const days = Math.floor(hours / 24);
		const hrs = hours % 24;
		return `${days}d ${hrs}h`;
	}
	return `${hours}h ${mins}m`;
}

export function formatDuration(startedAt: string | null | undefined, completedAt?: string | null): string | null {
	if (!startedAt) return null;
	const start = parseUTCDate(startedAt);
	const end = completedAt ? parseUTCDate(completedAt) : new Date();
	return formatSeconds(Math.floor((end.getTime() - start.getTime()) / 1000));
}

export function formatRelativeTime(dateString: string | null | undefined): string {
	if (!dateString) return '—';
	const date = parseUTCDate(dateString);
	const now = new Date();
	const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

	if (diffInSeconds < 60) return 'just now';
	if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
	if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
	if (diffInSeconds < 604800) return `${Math.floor(diffInSeconds / 86400)}d ago`;
	if (diffInSeconds < 2592000) return `${Math.floor(diffInSeconds / 604800)}w ago`;
	if (diffInSeconds < 31536000) return `${Math.floor(diffInSeconds / 2592000)}mo ago`;
	return `${Math.floor(diffInSeconds / 31536000)}y ago`;
}

export function formatRelativeTimeDetailed(dateString: string | null | undefined): string {
	if (!dateString) return '—';
	const date = parseUTCDate(dateString);
	const now = new Date();
	const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

	if (diffInSeconds < 60) return 'just now';
	if (diffInSeconds < 3600) {
		const minutes = Math.floor(diffInSeconds / 60);
		return `${minutes} ${minutes === 1 ? 'minute' : 'minutes'} ago`;
	}
	if (diffInSeconds < 86400) {
		const hours = Math.floor(diffInSeconds / 3600);
		const mins = Math.floor((diffInSeconds % 3600) / 60);
		const hLabel = hours === 1 ? 'hour' : 'hours';
		if (mins === 0) return `${hours} ${hLabel} ago`;
		return `${hours} ${hLabel}, ${mins} ${mins === 1 ? 'minute' : 'minutes'} ago`;
	}
	const days = Math.floor(diffInSeconds / 86400);
	const hours = Math.floor((diffInSeconds % 86400) / 3600);
	const dLabel = days === 1 ? 'day' : 'days';
	if (hours === 0) return `${days} ${dLabel} ago`;
	return `${days} ${dLabel}, ${hours} ${hours === 1 ? 'hour' : 'hours'} ago`;
}

export function formatDurationMs(ms: number): string {
	return formatSeconds(Math.round(ms / 1000));
}

/** tanstack-table sortingFn that sorts rows by a nullable ISO date field. */
export function byDate<T>(getField: (row: T) => string | null | undefined) {
	return (rowA: { original: T }, rowB: { original: T }) => {
		const a = getField(rowA.original);
		const b = getField(rowB.original);
		const ta = a ? new Date(a).getTime() : 0;
		const tb = b ? new Date(b).getTime() : 0;
		return ta - tb;
	};
}

export function formatNumber(num: number): string {
	if (num >= 1000) return (num / 1000).toFixed(1) + 'k';
	return num.toString();
}

/** Format ISO date as `YYYY-MM-DD`. */
export function formatStripDateFull(iso: string): string {
	const d = parseUTCDate(iso);
	if (isNaN(d.getTime())) return iso;
	const pad = (n: number) => n.toString().padStart(2, '0');
	return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
}

/** Format ISO date as `YYYY-MM`. */
export function formatStripDateShort(iso: string): string {
	const d = parseUTCDate(iso);
	if (isNaN(d.getTime())) return iso;
	const pad = (n: number) => n.toString().padStart(2, '0');
	return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}`;
}

const PANDAS_FREQ_MAP: Record<string, string> = {
	h: '1h',
	H: '1h',
	D: '1d',
	W: 'weekly',
	ME: 'monthly',
	M: 'monthly',
	MS: 'monthly',
	QE: 'quarterly',
	Q: 'quarterly',
	QS: 'quarterly',
	YS: 'yearly',
	YE: 'yearly',
	Y: 'yearly',
	A: 'yearly',
	AS: 'yearly',
};

/** Map a pandas freq alias to a human label. Returns null for null/undefined input. */
export function formatPandasFreq(freq: string | undefined | null): string | null {
	if (!freq) return null;
	if (PANDAS_FREQ_MAP[freq]) return PANDAS_FREQ_MAP[freq];
	const m = freq.match(/^(\d+)([A-Za-z]+)$/);
	if (m) {
		const n = m[1];
		const base = m[2];
		const mapped = PANDAS_FREQ_MAP[base];
		if (mapped) return `${n}${mapped.replace(/^1/, '')}`;
		return `${n}${base.toLowerCase()}`;
	}
	return freq;
}

export function slugify(name: string): string {
	return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

export function getJobLogPath(job: { log?: string; files?: { file_type: string; path: string }[] }): string | null {
	if (job.log) return job.log;
	return job.files?.find(f => f.file_type === 'LOG')?.path ?? null;
}

export function getTagType(tag: string | NetworkTag): TagType {
	if (typeof tag === 'string') return 'default';
	const name = tag.name?.toLowerCase() || '';
	const url = tag.url?.toLowerCase() || '';
	if (name.includes('config') || name.endsWith('.yaml') || name.endsWith('.yml')) return 'config';
	if (url.includes('/commit/') || /^[a-f0-9]{7,}$/.test(name) || name === 'master' || name === 'main') return 'version';
	return 'model';
}

export function getTagColor(type: TagType): TagColor {
	switch (type) {
		case 'model': return 'tag-model';
		case 'version': return 'tag-version';
		case 'config': return 'tag-config';
		default: return 'tag-default';
	}
}
