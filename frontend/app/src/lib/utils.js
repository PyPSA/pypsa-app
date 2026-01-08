import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
	return twMerge(clsx(inputs));
}

export function formatFileSize(bytes) {
	if (!bytes) return 'N/A';
	const mb = bytes / (1024 * 1024);
	return `${mb.toFixed(2)} MB`;
}

export function formatDate(dateString) {
	if (!dateString) return 'N/A';
	const date = new Date(dateString);
	return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

export function formatRelativeTime(dateString) {
	if (!dateString) return 'N/A';
	const date = new Date(dateString);
	const now = new Date();
	const diffInSeconds = Math.floor((now - date) / 1000);

	if (diffInSeconds < 60) return 'just now';
	if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
	if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
	if (diffInSeconds < 604800) return `${Math.floor(diffInSeconds / 86400)}d ago`;
	return date.toLocaleDateString();
}

export function formatNumber(num) {
	if (num >= 1000) return (num / 1000).toFixed(1) + 'k';
	return num.toString();
}

export function getDirectoryPath(fullPath) {
	if (!fullPath) return '';
	const parts = fullPath.split('/networks/');
	const relativePath = parts.length > 1 ? parts[parts.length - 1] : fullPath;
	const lastSlashIndex = relativePath.lastIndexOf('/');
	if (lastSlashIndex === -1) return '';
	return relativePath.substring(0, lastSlashIndex + 1);
}

export function getTagType(tag) {
	if (typeof tag === 'string') return 'default';
	const name = tag.name?.toLowerCase() || '';
	const url = tag.url?.toLowerCase() || '';
	if (name.includes('config') || name.endsWith('.yaml') || name.endsWith('.yml')) return 'config';
	if (url.includes('/commit/') || /^[a-f0-9]{7,}$/.test(name) || name === 'master' || name === 'main') return 'version';
	return 'model';
}

export function getTagColor(type) {
	switch (type) {
		case 'model': return 'tag-model';
		case 'version': return 'tag-version';
		case 'config': return 'tag-config';
		default: return 'tag-default';
	}
}
