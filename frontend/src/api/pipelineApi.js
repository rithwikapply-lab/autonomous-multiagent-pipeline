// Pipeline API client with configurable base URL via environment variable
const BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

export async function queryPipeline({
  query,
  top_k = 5,
  enable_reranking = true,
  enable_verification = true,
}) {
  const url = `${BASE_URL}/api/v1/query`;
  
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify({
      query,
      top_k,
      enable_reranking,
      enable_verification,
    }),
  });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) {
        errorDetail = typeof errJson.detail === 'string' 
          ? errJson.detail 
          : JSON.stringify(errJson.detail);
      }
    } catch (_) {}
    throw new Error(errorDetail);
  }

  return await response.json();
}

export async function checkBackendHealth() {
  try {
    const res = await fetch(`${BASE_URL}/health`, { method: 'GET' });
    if (!res.ok) return { online: false };
    const data = await res.json();
    return { online: true, data };
  } catch (err) {
    return { online: false, error: err.message };
  }
}

export async function ingestDocument({ title, text_content, metadata = {} }) {
  const url = `${BASE_URL}/api/v1/ingest`;
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify({
      title,
      text_content,
      metadata,
    }),
  });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) {
        errorDetail = typeof errJson.detail === 'string'
          ? errJson.detail
          : JSON.stringify(errJson.detail);
      }
    } catch (_) {}
    throw new Error(errorDetail);
  }

  return await response.json();
}

export async function fetchIndexedDocuments() {
  const url = `${BASE_URL}/api/v1/documents`;
  const response = await fetch(url, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch documents: HTTP ${response.status}`);
  }

  return await response.json();
}

export { BASE_URL };

