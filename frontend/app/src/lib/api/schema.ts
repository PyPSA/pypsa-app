// Lazy access to the backend OpenAPI spec for surfacing field descriptions.
// Fetched once per page load and memoised.

interface OpenAPISpec {
	components?: {
		schemas?: Record<string, SchemaObject>;
	};
}

interface SchemaObject {
	properties?: Record<string, PropertyObject>;
	description?: string;
	$ref?: string;
	anyOf?: Array<{ $ref?: string; type?: string }>;
}

interface PropertyObject extends SchemaObject {}

let cache: Promise<OpenAPISpec> | null = null;

function load(): Promise<OpenAPISpec> {
	if (!cache) {
		cache = fetch('/api/v1/openapi.json', { credentials: 'include' })
			.then((r) => (r.ok ? r.json() : Promise.reject(new Error(`openapi ${r.status}`))))
			.catch((err) => {
				cache = null;
				throw err;
			});
	}
	return cache;
}

function resolveRef(spec: OpenAPISpec, ref: string): SchemaObject | undefined {
	const name = ref.split('/').pop();
	return name ? spec.components?.schemas?.[name] : undefined;
}

function descend(spec: OpenAPISpec, current: SchemaObject, part: string): SchemaObject | undefined {
	const prop = current.properties?.[part];
	if (!prop) return undefined;
	if (prop.$ref) return resolveRef(spec, prop.$ref);
	const ref = prop.anyOf?.find((x) => x.$ref)?.$ref;
	if (ref) return resolveRef(spec, ref);
	return prop;
}

export async function fieldDescriptions(
	schema: string,
	fields: string[]
): Promise<Record<string, string>> {
	let spec: OpenAPISpec;
	try {
		spec = await load();
	} catch {
		return {};
	}
	const root = spec.components?.schemas?.[schema];
	if (!root) return {};
	const out: Record<string, string> = {};
	for (const field of fields) {
		const parts = field.split('.');
		let current: SchemaObject | undefined = root;
		for (let i = 0; i < parts.length - 1 && current; i++) {
			current = descend(spec, current, parts[i]);
		}
		const last = parts[parts.length - 1];
		const prop = current?.properties?.[last];
		if (prop?.description) out[field] = prop.description;
	}
	return out;
}
