import type { NetworkTag, TagType, TagColor } from "./types.js";

export { cn } from "$lib/lib/utils.js";

export function formatFileSize(bytes: number | null | undefined): string {
	if (!bytes) return '—';
	const mb = bytes / (1024 * 1024);
	return `${mb.toFixed(2)} MB`;
}

function parseUTCDate(dateString: string): Date {
	return new Date(dateString.endsWith('Z') ? dateString : dateString + 'Z');
}

export function formatDate(dateString: string | null | undefined): string {
	if (!dateString) return '—';
	const date = parseUTCDate(dateString);
	return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour12: false });
}

export function formatDuration(startedAt: string | null | undefined, completedAt?: string | null): string | null {
	if (!startedAt) return null;
	const start = parseUTCDate(startedAt);
	const end = completedAt ? parseUTCDate(completedAt) : new Date();
	const seconds = Math.floor((end.getTime() - start.getTime()) / 1000);
	if (seconds < 60) return `${seconds}s`;
	const minutes = Math.floor(seconds / 60);
	const secs = seconds % 60;
	if (minutes < 60) return `${minutes}m ${secs}s`;
	const hours = Math.floor(minutes / 60);
	const mins = minutes % 60;
	return `${hours}h ${mins}m`;
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
