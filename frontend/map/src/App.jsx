import React, { useState, useEffect } from 'react';
import { Routes, Route, useSearchParams, useNavigate } from 'react-router-dom';
import KeplerMap from './KeplerMap';

function NetworkMap() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const id = searchParams.get('id');
  const [datasets, setDatasets] = useState([]);
  const [config, setConfig] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [mapboxToken, setMapboxToken] = useState('');

  // Back URL
  const backUrl = id
    ? (import.meta.env.DEV ? `http://localhost:5173/network?id=${id}` : `/network?id=${id}`)
    : '/network';

  // Login URL - in dev mode, the SvelteKit app runs on port 5173
  const loginUrl = import.meta.env.DEV ? 'http://localhost:5173/login' : '/login';

  // Check authentication on mount
  useEffect(() => {
    async function checkAuth() {
      try {
        const response = await fetch('/api/v1/auth/me');
        // If we get 401, redirect to login (auth is enabled and user not authenticated)
        if (response.status === 401) {
          window.location.href = loginUrl;
        }
      } catch (err) {
        // Network errors - continue anyway (auth might be disabled)
        console.warn('Auth check failed:', err);
      }
    }

    checkAuth();
  }, []);

  useEffect(() => {
    // Fetch mapbox token from backend config
    async function fetchMapConfig() {
      try {
        const response = await fetch('/api/v1/map/config');
        if (response.ok) {
          const data = await response.json();
          setMapboxToken(data.mapbox_token || '');
        }
      } catch (err) {
        console.warn('Failed to fetch map config:', err);
        // Token will remain empty, map will show warning
      }
    }

    fetchMapConfig();
  }, []);

  useEffect(() => {
    // Poll task status until complete
    async function pollTaskStatus(statusUrl, maxAttempts = 60) {
      for (let i = 0; i < maxAttempts; i++) {
        const response = await fetch(statusUrl);

        // Check for auth errors
        if (response.status === 401) {
          window.location.href = loginUrl;
          return;
        }

        const result = await response.json();

        if (result.state === 'SUCCESS') {
          // Extract the actual data from the nested structure
          return result.result.data;
        } else if (result.state === 'FAILURE') {
          throw new Error(result.error || 'Task failed');
        }

        // Wait 1 second before next poll
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      throw new Error('Task timeout - data took too long to load');
    }

    // Fetch data from endpoint (handles both cached and task-based responses)
    async function fetchData(endpoint, dataType) {
      const response = await fetch(endpoint);
      if (!response.ok) {
        if (response.status === 401) {
          // User not authenticated - redirect to login
          window.location.href = loginUrl;
          return;
        }
        if (response.status === 404) {
          throw new Error(`Network "${id}" not found`);
        }
        throw new Error(`Failed to fetch ${dataType}: ${response.statusText}`);
      }

      const data = await response.json();

      // Check if it's a task (needs polling) or direct data (cached)
      if (data.status === 'processing' && data.task_id) {
        // Poll the task status until complete
        return await pollTaskStatus(data.status_url);
      } else {
        // Direct data (cached)
        return data;
      }
    }

    // Fetch network data from backend
    async function fetchNetworkData() {
      try {
        setLoading(true);
        setError(null);

        // Fetch both buses and lines in parallel
        const [busesData, linesData] = await Promise.all([
          fetchData(`/api/v1/map/${id}/buses`, 'buses'),
          fetchData(`/api/v1/map/${id}/lines`, 'lines')
        ]);

        const datasets = [];

        // Add buses dataset if we have any
        if (busesData.rows && busesData.rows.length > 0) {
          datasets.push({
            info: {
              id: 'buses',
              label: 'Network Buses'
            },
            data: {
              fields: busesData.fields,
              rows: busesData.rows
            }
          });
        }

        // Add lines dataset if we have data
        if (linesData.rows && linesData.rows.length > 0) {
          datasets.push({
            info: {
              id: 'lines',
              label: 'Network Lines'
            },
            data: {
              fields: linesData.fields,
              rows: linesData.rows
            }
          });
        }

        // Check if we have any data
        if (datasets.length === 0) {
          setError('No buses or lines found in this network');
          setLoading(false);
          return;
        }

        // Create Kepler.gl config with layers for each dataset
        const keplerConfig = {
          version: 'v1',
          config: {
            visState: {
              layers: []
            }
          }
        };

        // Add layer config for each dataset
        datasets.forEach((dataset, index) => {
          if (dataset.info.id === 'buses') {
            // Point layer for buses
            keplerConfig.config.visState.layers.push({
              id: `buses-layer`,
              type: 'point',
              config: {
                dataId: 'buses',
                label: 'Buses',
                color: [30, 150, 190],
                columns: {
                  lat: 'lat',
                  lng: 'lng'
                },
                isVisible: true,
                visConfig: {
                  radius: 5,
                  opacity: 0.8
                }
              }
            });
          } else if (dataset.info.id === 'lines') {
            // Line layer for lines
            keplerConfig.config.visState.layers.push({
              id: `lines-layer`,
              type: 'line',
              config: {
                dataId: 'lines',
                label: 'Lines',
                color: [255, 140, 0],
                columns: {
                  lat0: 'lat0',
                  lng0: 'lng0',
                  lat1: 'lat1',
                  lng1: 'lng1'
                },
                isVisible: true,
                visConfig: {
                  opacity: 0.6,
                  thickness: 2
                }
              }
            });
          }
        });

        setDatasets(datasets);
        setConfig(keplerConfig);
        setLoading(false);
      } catch (err) {
        console.error('Error fetching network data:', err);
        setError(err.message);
        setLoading(false);
      }
    }

    if (id) {
      fetchNetworkData();
    } else {
      // No ID provided, stop loading
      setLoading(false);
      setError('No network ID provided');
    }
  }, [id]);

  if (loading) {
    return (
      <div style={styles.center}>
        <div style={styles.spinner}></div>
        <p style={styles.text}>Loading network {id}...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.center}>
        <div style={styles.error}>
          <h2>Error Loading Network</h2>
          <p>{error}</p>
          <button onClick={() => window.location.href = backUrl} style={styles.button}>
            Go Back
          </button>
        </div>
      </div>
    );
  }

  if (!mapboxToken) {
    return (
      <div style={styles.center}>
        <div style={styles.warning}>
          <h2>Mapbox Token Required</h2>
          <p>To display the network map, configure a Mapbox access token in your environment.</p>
          <p style={styles.small}>
            Set <code>MAPBOX_TOKEN</code> environment variable when running the application.
          </p>
          <p style={styles.small}>
            Create a free account and obtain a token at <a href="https://www.mapbox.com/" target="_blank" rel="noopener">mapbox.com</a>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <button onClick={() => window.location.href = backUrl} style={styles.backButton}>
          ← Back
        </button>
        <h1 style={styles.title}>Network Map: {id}</h1>
      </div>
      <div style={styles.mapContainer}>
        <KeplerMap
          datasets={datasets}
          config={config}
          mapboxToken={mapboxToken}
        />
      </div>
    </div>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<NetworkMap />} />
      <Route path="*" element={<NetworkMap />} />
    </Routes>
  );
}

const styles = {
  container: {
    width: '100vw',
    height: '100vh',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden'
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '1rem',
    padding: '1rem 1.5rem',
    background: 'hsl(0 0% 100%)',
    borderBottom: '1px solid hsl(0 0% 89.8%)',
    boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.05)',
    zIndex: 1000
  },
  backButton: {
    padding: '0.5rem 1rem',
    background: 'hsl(0 0% 96.1%)',
    border: '1px solid hsl(0 0% 89.8%)',
    borderRadius: '0.375rem',
    cursor: 'pointer',
    fontSize: '0.875rem',
    fontWeight: '500',
    color: 'hsl(0 0% 3.9%)',
    transition: 'all 0.2s'
  },
  title: {
    margin: 0,
    fontSize: '1.25rem',
    fontWeight: '600',
    color: 'hsl(0 0% 3.9%)'
  },
  mapContainer: {
    flex: 1,
    position: 'relative',
    overflow: 'hidden'
  },
  center: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '100vw',
    height: '100vh',
    background: 'hsl(0 0% 100%)'
  },
  spinner: {
    width: '40px',
    height: '40px',
    border: '4px solid hsl(0 0% 96.1%)',
    borderTop: '4px solid hsl(155.71 87.5% 28.235%)',
    borderRadius: '50%',
    animation: 'spin 1s linear infinite'
  },
  text: {
    marginTop: '1rem',
    fontSize: '1rem',
    color: 'hsl(0 0% 45.1%)'
  },
  error: {
    textAlign: 'center',
    padding: '2rem',
    background: 'hsl(0 0% 100%)',
    borderRadius: '0.5rem',
    border: '1px solid hsl(0 0% 89.8%)',
    boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1)',
    maxWidth: '400px'
  },
  warning: {
    textAlign: 'center',
    padding: '2rem',
    background: '#fef3c7',
    borderRadius: '0.5rem',
    border: '1px solid #fbbf24',
    maxWidth: '500px'
  },
  button: {
    marginTop: '1rem',
    padding: '0.5rem 1rem',
    background: 'hsl(155.71 87.5% 28.235%)',
    color: 'hsl(0 0% 98%)',
    border: 'none',
    borderRadius: '0.375rem',
    cursor: 'pointer',
    fontSize: '0.875rem',
    fontWeight: '500',
    transition: 'all 0.2s'
  },
  small: {
    fontSize: '0.875rem',
    marginTop: '0.5rem'
  }
};

// Add keyframe animation for spinner and hover effects
const styleSheet = document.createElement('style');
styleSheet.textContent = `
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }

  button:hover {
    opacity: 0.85;
  }

  button:active {
    opacity: 0.7;
  }
`;
document.head.appendChild(styleSheet);

export default App;
