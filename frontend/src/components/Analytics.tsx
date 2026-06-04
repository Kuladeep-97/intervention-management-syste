import React, { useState, useMemo } from 'react';
import { Stage } from '../App';
import { ArrowLeft, Calendar, Users, Activity, Clock, MapPin } from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell, Legend
} from 'recharts';

// ─── Color Palette ───────────────────────────────────────────────────────
const COLORS = ['#4E47FF', '#19B6FF', '#FF6B6B', '#4CAF50', '#F59E0B', '#8B5CF6', '#EC4899'];
const TYPE_COLORS: Record<string, string> = {
  'Fallen Vial Recovery': '#4E47FF',
  'Stopper Adjustment': '#19B6FF',
  'Needle Replacement': '#FF6B6B',
  'Cleared Jam': '#4CAF50',
  'Environmental Monitoring': '#F59E0B',
  'Sensor Calibration': '#8B5CF6',
  'Other (SOP Exception)': '#EC4899',
};

// ─── Cooked Demo Data ────────────────────────────────────────────────────

interface DemoEvent {
  date: string;
  batch: string;
  port: string;
  type: string;
  duration_sec: number;
  operator: string;
}

const OPERATORS = ['Rajesh Kumar', 'Priya Sharma', 'Ankit Verma', 'Sneha Patel', 'Vikram Singh'];
const INTERVENTION_TYPES = [
  'Fallen Vial Recovery', 'Stopper Adjustment', 'Needle Replacement',
  'Cleared Jam', 'Environmental Monitoring', 'Sensor Calibration', 'Other (SOP Exception)'
];
const PORTS = ['Port 1', 'Port 2', 'Port 3'];
const BATCHES = ['#VFL-2024-001', '#VFL-2024-002', '#VFL-2024-003'];

function seedRandom(seed: number) {
  let s = seed;
  return () => { s = (s * 16807 + 0) % 2147483647; return (s - 1) / 2147483646; };
}

function generateDemoEvents(): DemoEvent[] {
  const events: DemoEvent[] = [];
  const rng = seedRandom(42);
  const startDate = new Date('2026-04-28');

  for (let day = 0; day < 14; day++) {
    const date = new Date(startDate);
    date.setDate(date.getDate() + day);
    const dateStr = date.toISOString().split('T')[0];
    const eventsPerDay = 8 + Math.floor(rng() * 12);

    for (let i = 0; i < eventsPerDay; i++) {
      events.push({
        date: dateStr,
        batch: BATCHES[Math.floor(rng() * BATCHES.length)],
        port: PORTS[Math.floor(rng() * PORTS.length)],
        type: INTERVENTION_TYPES[Math.floor(rng() * INTERVENTION_TYPES.length)],
        duration_sec: parseFloat((3 + rng() * 45).toFixed(1)),
        operator: OPERATORS[Math.floor(rng() * OPERATORS.length)],
      });
    }
  }
  return events;
}

const ALL_DEMO_EVENTS = generateDemoEvents();

// ─── Component ───────────────────────────────────────────────────────────

export function Analytics({ product, batch, onNavigate }: { product: string | null, batch: string | null, onNavigate: (s: Stage) => void }) {
  const allDates = [...new Set(ALL_DEMO_EVENTS.map(e => e.date))].sort();
  const [startDate, setStartDate] = useState(allDates[0]);
  const [endDate, setEndDate] = useState(allDates[allDates.length - 1]);

  const filteredEvents = useMemo(() =>
    ALL_DEMO_EVENTS.filter(e => e.date >= startDate && e.date <= endDate),
    [startDate, endDate]
  );

  // ── Intervention Type vs Frequency Over Days ──
  const typeOverDays = useMemo(() => {
    const map: Record<string, Record<string, number>> = {};
    filteredEvents.forEach(e => {
      if (!map[e.date]) map[e.date] = {};
      map[e.date][e.type] = (map[e.date][e.type] || 0) + 1;
    });
    return Object.keys(map).sort().map(date => {
      const label = new Date(date + 'T00:00:00').toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
      return { date: label, ...map[date] };
    });
  }, [filteredEvents]);

  // ── Batch-wise Aggregation ──
  const batchStats = useMemo(() => {
    const map: Record<string, { count: number; duration: number; types: Record<string, number> }> = {};
    filteredEvents.forEach(e => {
      if (!map[e.batch]) map[e.batch] = { count: 0, duration: 0, types: {} };
      map[e.batch].count++;
      map[e.batch].duration += e.duration_sec;
      map[e.batch].types[e.type] = (map[e.batch].types[e.type] || 0) + 1;
    });
    return Object.entries(map).map(([b, s]) => ({ batch: b, ...s }));
  }, [filteredEvents]);

  // ── Port-wise Frequency & Duration ──
  const portStats = useMemo(() => {
    const map: Record<string, { count: number; duration: number; types: Record<string, number>; operators: Set<string> }> = {};
    filteredEvents.forEach(e => {
      if (!map[e.port]) map[e.port] = { count: 0, duration: 0, types: {}, operators: new Set() };
      map[e.port].count++;
      map[e.port].duration += e.duration_sec;
      map[e.port].types[e.type] = (map[e.port].types[e.type] || 0) + 1;
      map[e.port].operators.add(e.operator);
    });
    return Object.entries(map).map(([port, s]) => ({
      port,
      count: s.count,
      duration: parseFloat(s.duration.toFixed(1)),
      avgDuration: parseFloat((s.duration / s.count).toFixed(1)),
      topType: Object.entries(s.types).sort((a, b) => b[1] - a[1])[0]?.[0] || 'None',
      operators: [...s.operators],
    }));
  }, [filteredEvents]);

  const portChartData = portStats.map(p => ({ name: p.port, Frequency: p.count, 'Avg Duration (s)': p.avgDuration }));

  // ── Operator Analytics ──
  const operatorStats = useMemo(() => {
    const map: Record<string, { count: number; duration: number; ports: Set<string>; types: Record<string, number> }> = {};
    filteredEvents.forEach(e => {
      if (!map[e.operator]) map[e.operator] = { count: 0, duration: 0, ports: new Set(), types: {} };
      map[e.operator].count++;
      map[e.operator].duration += e.duration_sec;
      map[e.operator].ports.add(e.port);
      map[e.operator].types[e.type] = (map[e.operator].types[e.type] || 0) + 1;
    });
    return Object.entries(map)
      .map(([name, s]) => ({
        name,
        count: s.count,
        duration: parseFloat(s.duration.toFixed(1)),
        avgDuration: parseFloat((s.duration / s.count).toFixed(1)),
        ports: [...s.ports].join(', '),
        topType: Object.entries(s.types).sort((a, b) => b[1] - a[1])[0]?.[0] || 'N/A',
      }))
      .sort((a, b) => b.count - a.count);
  }, [filteredEvents]);

  // ── Intervention Type Totals for Pie ──
  const typeTotals = useMemo(() => {
    const map: Record<string, number> = {};
    filteredEvents.forEach(e => { map[e.type] = (map[e.type] || 0) + 1; });
    return Object.entries(map).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);
  }, [filteredEvents]);

  const tooltipStyle = { borderRadius: '12px', border: '1px solid #e8e7ff', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' };

  return (
    <div className="space-y-6 pb-12 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-4">
          <button onClick={() => onNavigate('dashboard')} className="p-2 bg-white rounded-xl border border-[#e8e7ff] shadow-sm hover:bg-[#F4F4F6] transition-colors">
            <ArrowLeft className="w-5 h-5 text-[#232369]" />
          </button>
          <div>
            <h1 className="text-3xl font-bold text-[#232369] tracking-tight">Intervention Analytics</h1>
            <p className="text-sm text-gray-500 mt-1">Batch: <span className="font-semibold text-[#4E47FF]">{batch || 'All'}</span> · Product: <span className="font-semibold text-[#4E47FF]">{product || 'All'}</span></p>
          </div>
        </div>
        {/* Date Range Picker */}
        <div className="flex items-center space-x-3 bg-white px-4 py-2.5 rounded-xl border border-[#e8e7ff] shadow-sm">
          <Calendar className="w-4 h-4 text-[#4E47FF]" />
          <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
            className="text-sm border-none bg-transparent text-[#232369] font-medium outline-none" />
          <span className="text-gray-400">→</span>
          <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
            className="text-sm border-none bg-transparent text-[#232369] font-medium outline-none" />
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Interventions', value: filteredEvents.length, icon: Activity, color: '#4E47FF' },
          { label: 'Avg Duration', value: `${(filteredEvents.reduce((s, e) => s + e.duration_sec, 0) / (filteredEvents.length || 1)).toFixed(1)}s`, icon: Clock, color: '#F59E0B' },
          { label: 'Active Ports', value: new Set(filteredEvents.map(e => e.port)).size, icon: MapPin, color: '#4CAF50' },
          { label: 'Operators', value: new Set(filteredEvents.map(e => e.operator)).size, icon: Users, color: '#8B5CF6' },
        ].map(kpi => (
          <div key={kpi.label} className="bg-white p-5 rounded-2xl border border-[#e8e7ff] shadow-[0_2px_12px_rgba(78,71,255,0.08)] relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-1" style={{ backgroundColor: kpi.color }} />
            <div className="flex items-center space-x-2 mb-1">
              <kpi.icon className="w-4 h-4" style={{ color: kpi.color }} />
              <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">{kpi.label}</span>
            </div>
            <p className="text-3xl font-black text-[#232369]">{kpi.value}</p>
          </div>
        ))}
      </div>

      {/* Intervention Type vs Frequency Over Days (Stacked Bar) */}
      <div className="bg-white p-6 rounded-2xl border border-[#e8e7ff] shadow-[0_2px_12px_rgba(78,71,255,0.08)]">
        <h3 className="text-lg font-bold text-[#232369] mb-6">Intervention Type Frequency Over Days</h3>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={typeOverDays}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e8e7ff" />
              <XAxis dataKey="date" stroke="#6b7280" fontSize={12} />
              <YAxis stroke="#6b7280" fontSize={12} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: '12px' }} />
              {INTERVENTION_TYPES.map(type => (
                <Bar key={type} dataKey={type} stackId="a" fill={TYPE_COLORS[type] || '#999'} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Intervention Type Distribution (Pie) */}
        <div className="bg-white p-6 rounded-2xl border border-[#e8e7ff] shadow-[0_2px_12px_rgba(78,71,255,0.08)]">
          <h3 className="text-lg font-bold text-[#232369] mb-6">Intervention Type Distribution</h3>
          <div className="h-72 flex items-center">
            <div className="flex-1 h-full">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={typeTotals} cx="50%" cy="50%" innerRadius={55} outerRadius={95} paddingAngle={3} dataKey="value">
                    {typeTotals.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex flex-col space-y-1.5 ml-2">
              {typeTotals.map((t, i) => (
                <div key={t.name} className="flex items-center space-x-2">
                  <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                  <span className="text-xs font-medium text-[#232369] truncate max-w-[140px]">{t.name} ({t.value})</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Port-wise Frequency & Avg Duration (Bar Chart) */}
        <div className="bg-white p-6 rounded-2xl border border-[#e8e7ff] shadow-[0_2px_12px_rgba(78,71,255,0.08)]">
          <h3 className="text-lg font-bold text-[#232369] mb-6">Port-wise Frequency & Avg Duration</h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={portChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e8e7ff" />
                <XAxis dataKey="name" stroke="#6b7280" fontSize={12} />
                <YAxis stroke="#6b7280" fontSize={12} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: '12px' }} />
                <Bar dataKey="Frequency" fill="#4E47FF" radius={[6, 6, 0, 0]} />
                <Bar dataKey="Avg Duration (s)" fill="#F59E0B" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Port-wise Detailed Table */}
      <div className="bg-white p-6 rounded-2xl border border-[#e8e7ff] shadow-[0_2px_12px_rgba(78,71,255,0.08)]">
        <h3 className="text-lg font-bold text-[#232369] mb-4">Port-wise Intervention Breakdown</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-[#e8e7ff]">
                <th className="pb-3 pt-2 px-4 font-semibold text-gray-500 uppercase text-xs tracking-wider">Port</th>
                <th className="pb-3 pt-2 px-4 font-semibold text-gray-500 uppercase text-xs tracking-wider">Total</th>
                <th className="pb-3 pt-2 px-4 font-semibold text-gray-500 uppercase text-xs tracking-wider">Total Duration</th>
                <th className="pb-3 pt-2 px-4 font-semibold text-gray-500 uppercase text-xs tracking-wider">Avg Duration</th>
                <th className="pb-3 pt-2 px-4 font-semibold text-gray-500 uppercase text-xs tracking-wider">Top Type</th>
                <th className="pb-3 pt-2 px-4 font-semibold text-gray-500 uppercase text-xs tracking-wider">Operators</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#e8e7ff]">
              {portStats.map(p => (
                <tr key={p.port} className="hover:bg-[#F4F4F6]/50 transition-colors">
                  <td className="py-4 px-4 text-sm font-semibold text-[#4E47FF]">{p.port}</td>
                  <td className="py-4 px-4 text-sm font-medium text-[#232369]">{p.count}</td>
                  <td className="py-4 px-4 text-sm text-gray-600">{p.duration}s</td>
                  <td className="py-4 px-4 text-sm text-gray-600">{p.avgDuration}s</td>
                  <td className="py-4 px-4">
                    <span className="text-xs font-medium px-2 py-1 rounded-full text-white" style={{ backgroundColor: TYPE_COLORS[p.topType] || '#999' }}>
                      {p.topType}
                    </span>
                  </td>
                  <td className="py-4 px-4 text-sm text-gray-600">{p.operators.join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Batch-wise Summary */}
      <div className="bg-white p-6 rounded-2xl border border-[#e8e7ff] shadow-[0_2px_12px_rgba(78,71,255,0.08)]">
        <h3 className="text-lg font-bold text-[#232369] mb-4">Batch-wise Intervention Summary</h3>
        <div className="grid md:grid-cols-3 gap-4">
          {batchStats.map(b => {
            const topTypes = Object.entries(b.types).sort((a, c) => c[1] - a[1]).slice(0, 3);
            return (
              <div key={b.batch} className="bg-[#F4F4F6] p-5 rounded-xl border border-[#e8e7ff]">
                <p className="text-sm font-bold text-[#4E47FF] mb-2">{b.batch}</p>
                <div className="space-y-1 text-sm text-[#232369]">
                  <p>Interventions: <span className="font-bold">{b.count}</span></p>
                  <p>Total Duration: <span className="font-bold">{b.duration.toFixed(1)}s</span></p>
                  <p>Avg Duration: <span className="font-bold">{(b.duration / b.count).toFixed(1)}s</span></p>
                </div>
                <div className="mt-3 pt-3 border-t border-[#e8e7ff]">
                  <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Top Types</p>
                  {topTypes.map(([type, count]) => (
                    <div key={type} className="flex justify-between text-xs text-gray-600 mt-1">
                      <span className="truncate mr-2">{type}</span>
                      <span className="font-semibold text-[#232369]">{count}</span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Operator-wise Table */}
      <div className="bg-white p-6 rounded-2xl border border-[#e8e7ff] shadow-[0_2px_12px_rgba(78,71,255,0.08)]">
        <div className="flex items-center space-x-3 mb-4">
          <Users className="w-5 h-5 text-[#8B5CF6]" />
          <h3 className="text-lg font-bold text-[#232369]">Operator-wise Intervention Log</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-[#e8e7ff]">
                <th className="pb-3 pt-2 px-4 font-semibold text-gray-500 uppercase text-xs tracking-wider">Operator</th>
                <th className="pb-3 pt-2 px-4 font-semibold text-gray-500 uppercase text-xs tracking-wider">Interventions</th>
                <th className="pb-3 pt-2 px-4 font-semibold text-gray-500 uppercase text-xs tracking-wider">Total Duration</th>
                <th className="pb-3 pt-2 px-4 font-semibold text-gray-500 uppercase text-xs tracking-wider">Avg Duration</th>
                <th className="pb-3 pt-2 px-4 font-semibold text-gray-500 uppercase text-xs tracking-wider">Ports Accessed</th>
                <th className="pb-3 pt-2 px-4 font-semibold text-gray-500 uppercase text-xs tracking-wider">Most Frequent Type</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#e8e7ff]">
              {operatorStats.map(op => (
                <tr key={op.name} className="hover:bg-[#F4F4F6]/50 transition-colors">
                  <td className="py-4 px-4">
                    <div className="flex items-center space-x-2">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#6661FF] to-[#4E47FF] flex items-center justify-center text-white text-xs font-bold">
                        {op.name.split(' ').map(n => n[0]).join('')}
                      </div>
                      <span className="text-sm font-semibold text-[#232369]">{op.name}</span>
                    </div>
                  </td>
                  <td className="py-4 px-4 text-sm font-medium text-[#232369]">{op.count}</td>
                  <td className="py-4 px-4 text-sm text-gray-600">{op.duration}s</td>
                  <td className="py-4 px-4 text-sm text-gray-600">{op.avgDuration}s</td>
                  <td className="py-4 px-4 text-sm text-gray-600">{op.ports}</td>
                  <td className="py-4 px-4">
                    <span className="text-xs font-medium px-2 py-1 rounded-full text-white" style={{ backgroundColor: TYPE_COLORS[op.topType] || '#999' }}>
                      {op.topType}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
