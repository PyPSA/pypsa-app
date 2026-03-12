import { browser } from '$app/environment';
import type { VisibilityState } from '@tanstack/table-core';
import type { NetworkTag, TagType, TagColor, User } from "./types.js";
import type { FilterOption } from '$lib/components/ui/filter-dialog';

export { cn } from "$lib/lib/utils.js";

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
 * Build owner filter options with the current user listed first.
 */
export function buildOwnerOptions(availableOwners: User[], currentUserId?: string): FilterOption[] {
	const opts: FilterOption[] = [];
	const currentUserInOwners = availableOwners.find(o => o.id === currentUserId);
	if (currentUserInOwners) {
		opts.push({ id: currentUserInOwners.id, label: currentUserInOwners.username, avatarUrl: currentUserInOwners.avatar_url });
	}
	for (const owner of availableOwners) {
		if (owner.id !== currentUserId) {
			opts.push({ id: owner.id, label: owner.username, avatarUrl: owner.avatar_url });
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

function parseUTCDate(dateString: string): Date {
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
	return date.toLocaleDateString();
}

export function formatDurationMs(ms: number): string {
	return formatSeconds(Math.round(ms / 1000));
}

export function formatNumber(num: number): string {
	if (num >= 1000) return (num / 1000).toFixed(1) + 'k';
	return num.toString();
}

export function getDirectoryPath(fullPath: string | null | undefined): string {
	if (!fullPath) return '';
	const parts = fullPath.split('/networks/');
	const relativePath = parts.length > 1 ? parts[parts.length - 1] : fullPath;
	const lastSlashIndex = relativePath.lastIndexOf('/');
	if (lastSlashIndex === -1) return '';
	return relativePath.substring(0, lastSlashIndex + 1);
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
