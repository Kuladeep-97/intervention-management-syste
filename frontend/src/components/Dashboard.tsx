import React, { useState, useEffect } from 'react';
import { getProducts } from '../constants';
import { Stage } from '../App';
import { AlertTriangle, Play, Save, X } from 'lucide-react';
import { 
  fetchEvents, fetchSummary, fetchClips, fetchDeviations, saveClassifications,
  clipUrl, snapshotUrl, VIDEO_FEED_URL, resetStream,
  InterventionEvent, Summary, ClipInfo, Deviation, PortStat
} from '../api';

export function Dashboard({ product, batch, onNavigate }: { product: string | null, batch: string | null, onNavigate: (s: Stage) => void }) {
  const products = getProducts();
  const productObj = products.find(p => p.id === product);
  const interventions = productObj?.interventions || [];

  const [classifications, setClassifications] = useState<Record<number, string>>({});
  const [selectedEventIndex, setSelectedEventIndex] = useState<number | null>(null);
  const [camera, setCamera] = useState('Camera 1');

  const [events, setEvents] = useState<InterventionEvent[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [clips, setClips] = useState<ClipInfo[]>([]);
  const [deviations, setDeviations] = useState<Deviation[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);

  useEffect(() => {
    // Reset backend cache when dashboard is freshly loaded/refreshed
    resetStream().catch(() => {});
  }, []);

  const loadData = async () => {
    try {
      const [evData, sumData, clipData, devData, streamData] = await Promise.all([
        fetchEvents(), fetchSummary(), fetchClips(), fetchDeviations(),
        fetch(`${'/api'}/stream/status`).then(r => r.json()).catch(() => ({ is_running: false }))
      ]);
      const isRunning = !!streamData.is_running;
      const activeEvents = isRunning && streamData.events ? streamData.events : evData;
      const activeDeviations = isRunning && streamData.deviations ? streamData.deviations : devData;

      // Always use sumData (full shape) as the base.
      // If streaming, overlay the live counts on top — never replace entirely,
      // so fields like frequency_per_min / max_count / count_usage_pct are
      // never undefined when the MetricCards call .toString() on them.
      const activeSummary = isRunning && streamData.summary
        ? {
            ...sumData,                            // full shape with all computed fields
            total_events: streamData.summary.total_events ?? sumData.total_events,
            total_duration_sec: streamData.summary.total_duration_sec ?? sumData.total_duration_sec,
            port_stats: streamData.summary.port_stats ?? streamData.summary.events_by_port ?? sumData.port_stats ?? {},
          }
        : sumData;

      setEvents(activeEvents);
      setSummary(activeSummary);
      setClips(clipData);
      setDeviations(activeDeviations);
      // Removed setIsStreaming(isRunning) to prevent race condition when user clicks start stream

      const loadedClassifications: Record<number, string> = {};
      activeEvents.forEach((ev, idx) => {
        if (ev.intervention_type && ev.intervention_type !== 'Unclassified') {
          loadedClassifications[idx] = ev.intervention_type;
        }
      });
      setClassifications(prev => {
        return { ...loadedClassifications, ...prev };
      });
    } catch (err) {
      console.error("Failed to fetch dashboard data:", err);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, isStreaming ? 1000 : 3000);
    return () => clearInterval(interval);
  }, [isStreaming]);

  const handleStartStream = async () => {
    setIsStreaming(true);
  };

  const handleStopStream = async () => {
    setIsStreaming(false);
  };

  useEffect(() => {
    let ws: WebSocket | null = null;
    if (isStreaming) {
      ws = new WebSocket(`ws://${window.location.hostname}:8000/ws/video`);
      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.image) {
            const img = document.getElementById('live-video-feed') as HTMLImageElement;
            if (img) {
              img.src = `data:image/jpeg;base64,${payload.image}`;
            }
          }
          if (payload.metrics) {
            setSummary(prev => {
              if (!prev) return null;
              return {
                ...prev,
                total_events: payload.metrics.in_count !== undefined ? payload.metrics.in_count : prev.total_events,
              };
            });
          }
        } catch (err) {}
      };
      ws.onclose = () => {
        setIsStreaming(false);
      };
    }
    return () => {
      if (ws) ws.close();
    };
  }, [isStreaming]);

  const handleSaveClassifications = async () => {
    try {
      await saveClassifications(classifications);
      alert("Classifications saved successfully.");
    } catch (err) {
      console.error(err);
      alert("Failed to save classifications.");
    }
  };

  const getExpectedClipUrl = (ev: InterventionEvent) => {
    // 1. Try to match using clip_path directly if available in metadata
    const clipPath = (ev as any).clip_path;
    if (clipPath) {
      const filename = clipPath.split(/[\\/]/).pop();
      const clip = clips.find(c => c.filename === filename);
      if (clip) return clip.url;
    }

    // 2. Fallback: match using snapshot path replacement
    if (!ev.snapshot_path) return null;
    const expectedFilename = ev.snapshot_path.split(/[\\/]/).pop()?.replace('.jpg', '.mp4');
    const clip = clips.find(c => c.filename === expectedFilename);
    return clip ? clip.url : null;
  };

  const hasCriticalDeviations = deviations.some(d => d.severity === 'HIGH');

  return (
    <div className="space-y-6 pb-12 relative">
      {/* Critical Alarm Banner */}
      {summary?.has_deviations && hasCriticalDeviations && (
        <div 
          onClick={() => onNavigate('analytics')}
          className="cursor-pointer rounded-xl p-4 text-white shadow-lg flex items-center justify-center space-x-3 hover:opacity-90 transition-opacity animate-pulse"
          style={{ background: 'linear-gradient(135deg, #6661FF, #4E47FF, #232369)' }}
        >
          <AlertTriangle className="w-6 h-6" />
          <div className="text-center">
            <h3 className="font-bold text-lg">🚨 CRITICAL DEVIATION: REGULATORY LIMIT EXCEEDED 🚨</h3>
            <p className="text-sm opacity-90">Immediate QA Review Required. Validating standard operating procedures...</p>
          </div>
        </div>
      )}

      {/* Top Summary Metrics */}
      {summary ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <MetricCard title="Total Interventions" value={summary.total_events.toString()} sub={`limit ${summary.max_count}`} status={summary.count_usage_pct >= 100 ? 'red' : summary.count_usage_pct >= 80 ? 'amber' : 'green'} />
          <MetricCard title="Total Duration" value={`${summary.total_duration_sec}s`} sub={`limit ${summary.max_duration_sec}s`} status={summary.duration_usage_pct >= 100 ? 'red' : summary.duration_usage_pct >= 80 ? 'amber' : 'green'} />
          <MetricCard title="Count Usage" value={`${summary.count_usage_pct}%`} sub="of allowed limit" status={summary.count_usage_pct >= 100 ? 'red' : summary.count_usage_pct >= 80 ? 'amber' : 'green'} />
          <MetricCard title="Duration Usage" value={`${summary.duration_usage_pct}%`} sub="of allowed limit" status={summary.duration_usage_pct >= 100 ? 'red' : summary.duration_usage_pct >= 80 ? 'amber' : 'green'} />
          <MetricCard title="Avg Duration" value={`${summary.avg_duration_sec}s`} sub="per event" status="amber" />
          <MetricCard title="Frequency" value={summary.frequency_per_min.toString()} sub="events/min" status="amber" />
        </div>
      ) : (
        <div className="h-24 bg-gray-100 animate-pulse rounded-xl"></div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Live Feed Section */}
          <div className="bg-white rounded-2xl border border-[#e8e7ff] shadow-[0_2px_12px_rgba(78,71,255,0.08)] overflow-hidden">
            <div className="bg-[#F4F4F6] border-b border-[#e8e7ff] px-4 py-3 flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className="flex items-center space-x-2">
                  <div className={`w-2.5 h-2.5 rounded-full ${isStreaming ? 'bg-red-500 animate-pulse' : 'bg-gray-400'}`} />
                  <span className="text-sm font-bold text-[#232369]">{isStreaming ? 'LIVE' : 'IDLE'}</span>
                </div>
                {!isStreaming ? (
                  <button 
                    onClick={handleStartStream}
                    className="text-[10px] bg-[#4E47FF] text-white px-3 py-1 rounded font-bold hover:opacity-80 transition-opacity flex items-center space-x-1"
                  >
                    <Play className="w-3 h-3" />
                    <span>START STREAM</span>
                  </button>
                ) : (
                  <button 
                    onClick={handleStopStream}
                    className="text-[10px] bg-red-600 text-white px-3 py-1 rounded font-bold hover:opacity-80 transition-opacity"
                  >
                    STOP STREAM
                  </button>
                )}
              </div>
              <span className="text-sm font-medium text-[#6661FF] hidden sm:inline">Batch: {batch} | Port Monitoring</span>
              <select 
                value={camera} 
                onChange={e => setCamera(e.target.value)}
                className="text-sm font-mono text-[#232369] bg-transparent border border-[#e8e7ff] rounded-md px-2 py-1 outline-none focus:ring-1 focus:ring-[#4E47FF]"
              >
                {[1, 2, 3, 4].map(num => (
                  <option key={num} value={`Camera ${num}`}>Camera {num}</option>
                ))}
              </select>
            </div>
            <div className="bg-[#0d0d1a] aspect-video w-full flex items-center justify-center border-b-[2px] border-[#4E47FF] relative">
              {!isStreaming && (
                <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-500 z-0">
                  <Play className="w-16 h-16 mb-4 opacity-50" />
                  <span className="text-lg font-bold tracking-widest">STREAM OFFLINE</span>
                  <span className="text-sm mt-2">Click START STREAM to connect to the pipeline</span>
                </div>
              )}
              <img 
                id="live-video-feed" 
                alt="Live Stream" 
                className="w-full h-full object-contain absolute top-0 left-0" 
                style={{ opacity: isStreaming ? 1 : 0, zIndex: isStreaming ? 10 : 0 }} 
              />
            </div>
          </div>

          {/* Intervention Clips Gallery */}
          <div>
            <h3 className="text-lg font-semibold text-[#232369] mb-3">Intervention Clips</h3>
            <div className="flex overflow-x-auto space-x-4 pb-4 scrollbar-thin scrollbar-thumb-[#4E47FF] scrollbar-track-[#e8e7ff]">
              {events.slice().reverse().map((ev, iOriginalRev) => {
                const i = events.length - 1 - iOriginalRev;
                const hasClip = getExpectedClipUrl(ev) !== null;
                return (
                <div 
                  key={i} 
                  onClick={() => hasClip && setSelectedEventIndex(i)}
                  className={`flex-none w-64 bg-white rounded-xl border border-[#e8e7ff] shadow-[0_2px_12px_rgba(78,71,255,0.08)] overflow-hidden transition-transform ${hasClip ? 'hover:-translate-y-1 cursor-pointer' : 'opacity-75'}`}
                >
                  <div className="h-32 bg-[#0d0d1a] relative flex items-center justify-center group overflow-hidden">
                    {ev.snapshot_path && <img src={snapshotUrl(ev.snapshot_path)} alt="Snapshot" className="absolute inset-0 w-full h-full object-cover opacity-60" />}
                    {hasClip && <Play className="w-8 h-8 text-white opacity-80 group-hover:opacity-100 transition-opacity relative z-10" />}
                    <div className="absolute top-2 left-2 bg-[#6661FF] text-white text-[10px] font-bold px-2 py-1 rounded z-10">{ev.roi_label}</div>
                    <div className="absolute bottom-2 right-2 bg-black/70 text-white text-[10px] font-mono px-2 py-1 rounded z-10">{ev.duration_sec}s</div>
                  </div>
                  <div className="p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-semibold text-[#232369]">Event #{ev.event_id}</span>
                      <span className="text-xs bg-[#F4F4F6] text-[#6661FF] px-2 py-0.5 rounded-full">{ev.start_time}</span>
                    </div>
                    <div className="text-xs text-gray-500 truncate">{classifications[i] || ev.intervention_type || 'Unclassified'}</div>
                  </div>
                </div>
              )})}
              {events.length === 0 && <p className="text-sm text-gray-500 italic">No interventions detected yet.</p>}
            </div>
            <p className="text-xs text-gray-500 mt-1">📂 {clips.length} clips and {events.length} events recorded this session</p>
          </div>
        </div>

        {/* Right Column */}
        <div className="space-y-6">
          {/* Deviation Alerts Panel */}
          <div className="bg-white rounded-2xl border border-[#e8e7ff] shadow-[0_2px_12px_rgba(78,71,255,0.08)] p-5">
            <h3 className="text-lg font-semibold text-[#232369] mb-4">Deviation Alerts</h3>
            <div className="space-y-3">
              {deviations.map((dev, idx) => (
                <div key={idx} className={`p-3 rounded-xl border ${dev.severity === 'HIGH' ? 'bg-red-50 border-red-100' : 'bg-amber-50 border-amber-100'}`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-xs font-bold px-2 py-1 rounded-full ${dev.severity === 'HIGH' ? 'text-red-600 bg-red-100' : 'text-amber-600 bg-amber-100'}`}>
                      {dev.severity}
                    </span>
                    <span className={`text-xs ${dev.severity === 'HIGH' ? 'text-red-500' : 'text-amber-500'}`}>{dev.trigger_time}</span>
                  </div>
                  <p className={`text-sm font-semibold ${dev.severity === 'HIGH' ? 'text-red-700' : 'text-amber-700'}`}>{dev.type}</p>
                  <p className={`text-xs mt-1 ${dev.severity === 'HIGH' ? 'text-red-600' : 'text-amber-600'}`}>{dev.message}</p>
                </div>
              ))}
              {deviations.length === 0 && (
                <p className="text-sm text-gray-600 italic">No deviations reported.</p>
              )}
            </div>
          </div>

          {/* Per-Port Statistics */}
          <div className="bg-white rounded-2xl border border-[#e8e7ff] shadow-[0_2px_12px_rgba(78,71,255,0.08)] p-5">
            <h3 className="text-lg font-semibold text-[#232369] mb-4">Port Statistics</h3>
            <div className="space-y-4">
              {summary && Object.entries(summary.port_stats || summary.events_by_port || {}).map(([port, stat]) => {
                const pStat = stat as PortStat;
                const pct = summary.total_events > 0 ? (pStat.count / summary.total_events) * 100 : 0;
                return (
                <div key={port}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-medium text-[#232369]">{port}</span>
                    <span className="text-gray-500">{pStat.count} events ({Math.round(pStat.total_duration_sec)}s)</span>
                  </div>
                  <div className="w-full bg-[#F4F4F6] rounded-full h-2">
                    <div className="bg-[#4E47FF] h-2 rounded-full transition-all duration-500" style={{ width: `${pct}%` }}></div>
                  </div>
                </div>
              )})}
            </div>
          </div>
        </div>
      </div>

      {/* Intervention Classification Table */}
      <div className="bg-white rounded-2xl border border-[#e8e7ff] shadow-[0_2px_12px_rgba(78,71,255,0.08)] p-5">
        <h3 className="text-lg font-semibold text-[#232369] mb-4">Intervention Classification (HITL Review)</h3>
        <div className="overflow-x-auto max-h-96">
          <table className="w-full text-left border-collapse relative">
            <thead className="sticky top-0 bg-white z-10 shadow-sm border-b border-[#e8e7ff]">
              <tr className="text-sm text-gray-500">
                <th className="pb-3 font-medium">Event ID</th>
                <th className="pb-3 font-medium">Port</th>
                <th className="pb-3 font-medium">Status</th>
                <th className="pb-3 font-medium">Start Time</th>
                <th className="pb-3 font-medium">End Time</th>
                <th className="pb-3 font-medium">Duration (s)</th>
                <th className="pb-3 font-medium">Intervention Type</th>
                <th className="pb-3 font-medium">Video Clip</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {events.slice().reverse().map((ev, iOriginalRev) => {
                const i = events.length - 1 - iOriginalRev;
                const clipUrlStr = getExpectedClipUrl(ev);
                return (
                <tr key={i} className="border-b border-[#e8e7ff] last:border-0 hover:bg-[#F4F4F6]/50 transition-colors">
                  <td className="py-3 text-[#232369] font-medium">{ev.event_id}</td>
                  <td className="py-3 text-gray-600">{ev.roi_label}</td>
                  <td className="py-3 text-gray-600 font-semibold text-xs">
                    <span className={`px-2 py-1 rounded-full ${ev.intervention_type === 'In Progress' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
                      {ev.intervention_type === 'In Progress' ? 'Active' : 'Idle'}
                    </span>
                  </td>
                  <td className="py-3 text-gray-600 font-mono">{ev.start_time}</td>
                  <td className="py-3 text-gray-600 font-mono">{ev.end_time}</td>
                  <td className="py-3 text-gray-600 font-mono">{typeof ev.duration_sec === 'number' ? ev.duration_sec.toFixed(2) : ev.duration_sec}</td>
                  <td className="py-3">
                    <select 
                      className="w-full max-w-xs p-2 border border-[#e8e7ff] rounded-lg focus:ring-2 focus:ring-[#4E47FF] outline-none bg-white text-[#232369]"
                      value={classifications[i] || ev.intervention_type || ''}
                      onChange={(e) => setClassifications({...classifications, [i]: e.target.value})}
                    >
                      <option value="">-- Select Type --</option>
                      {interventions.map(type => (
                        <option key={type} value={type}>{type}</option>
                      ))}
                    </select>
                  </td>
                  <td className="py-3">
                    {clipUrlStr ? (
                      <button 
                        onClick={() => setSelectedEventIndex(i)}
                        className="text-[#4E47FF] hover:text-[#232369] flex items-center space-x-1 font-medium"
                      >
                        <Play className="w-4 h-4" />
                        <span>Review</span>
                      </button>
                    ) : (
                      <span className="text-gray-400 font-mono text-xs">No Clip</span>
                    )}
                  </td>
                </tr>
              )})}
            </tbody>
          </table>
        </div>
        <div className="mt-6 flex justify-end">
          <button 
            onClick={handleSaveClassifications}
            className="flex items-center space-x-2 px-6 py-2.5 rounded-xl font-semibold text-white transition-all hover:-translate-y-0.5 shadow-md"
            style={{ background: 'linear-gradient(135deg, #6661FF, #4E47FF, #232369)' }}
          >
            <Save className="w-4 h-4" />
            <span>Save Classifications</span>
          </button>
        </div>
      </div>

      {/* Clip Modal */}
      {selectedEventIndex !== null && events[selectedEventIndex] && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl border border-[#e8e7ff] shadow-2xl w-full max-w-3xl overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-[#e8e7ff]">
              <h3 className="text-lg font-bold text-[#232369]">Review Intervention Clip - Event #{events[selectedEventIndex].event_id} ({events[selectedEventIndex].roi_label})</h3>
              <button 
                onClick={() => setSelectedEventIndex(null)}
                className="p-1 hover:bg-[#F4F4F6] rounded-lg transition-colors"
              >
                <X className="w-6 h-6 text-gray-500" />
              </button>
            </div>
            <div className="p-6 space-y-6">
              <div className="bg-[#0d0d1a] aspect-video w-full rounded-xl flex items-center justify-center relative overflow-hidden">
                <video 
                  src={getExpectedClipUrl(events[selectedEventIndex]) || ''} 
                  controls 
                  autoPlay 
                  className="w-full h-full"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-[#232369] mb-2">Classify Intervention</label>
                <select 
                  className="w-full p-3 border border-[#e8e7ff] rounded-xl focus:ring-2 focus:ring-[#4E47FF] outline-none bg-[#F4F4F6] text-[#232369]"
                  value={classifications[selectedEventIndex] || events[selectedEventIndex].intervention_type || ''}
                  onChange={(e) => setClassifications({...classifications, [selectedEventIndex]: e.target.value})}
                >
                  <option value="">-- Select Type --</option>
                  {interventions.map(type => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>
              </div>
              
              <div className="flex justify-end space-x-3">
                <button 
                  onClick={() => setSelectedEventIndex(null)}
                  className="px-6 py-2.5 rounded-xl font-semibold text-gray-600 bg-[#F4F4F6] hover:bg-gray-200 transition-colors"
                >
                  Cancel
                </button>
                <button 
                  onClick={async () => {
                   try {
                     await saveClassifications(classifications);
                     setSelectedEventIndex(null);
                   } catch (e) {
                     alert("Failed to save.");
                   }
                  }}
                  className="px-6 py-2.5 rounded-xl font-semibold text-white transition-all hover:-translate-y-0.5 shadow-md"
                  style={{ background: 'linear-gradient(135deg, #6661FF, #4E47FF, #232369)' }}
                >
                  Save & Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCard({ title, value, sub, status }: { title: string, value: string, sub: string, status: 'green' | 'amber' | 'red' }) {
  const borderColors = {
    green: 'border-[#22c55e]',
    amber: 'border-[#f59e0b]',
    red: 'border-[#ef4444]',
  };

  return (
    <div className={`bg-white p-4 rounded-xl border ${borderColors[status]} shadow-[0_2px_12px_rgba(78,71,255,0.08)] hover:-translate-y-1 transition-transform relative overflow-hidden`}>
      <div className={`absolute top-0 left-0 w-full h-1 bg-${status}-500`} />
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">{title}</p>
      <div className="text-3xl font-black tracking-tight mb-1" style={{ background: 'linear-gradient(135deg, #6661FF, #4E47FF, #232369)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
        {value}
      </div>
      <p className="text-xs text-gray-400 font-medium">{sub}</p>
    </div>
  );
}
