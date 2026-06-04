import React, { useState, useEffect } from 'react';
import { Lock, Save, Settings, ShieldAlert, Sliders, CheckCircle } from 'lucide-react';
import { getProducts, saveProducts } from '../constants';
import { fetchConfig, saveConfig, AppConfig } from '../api';

export function AdminSettings({ product }: { product: string | null }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  
  const [products, setProducts] = useState(getProducts());
  const [selectedProductId, setSelectedProductId] = useState(product || products[0].id);
  const [newIntervention, setNewIntervention] = useState('');
  const [showSaved, setShowSaved] = useState(false);

  const [config, setConfig] = useState<AppConfig | null>(null);
  const [selectedRoiIndex, setSelectedRoiIndex] = useState(0);

  useEffect(() => {
    fetchConfig().then(setConfig).catch(console.error);
  }, []);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (password === 'QA_ADMIN_2024') {
      setIsAuthenticated(true);
      setError('');
    } else {
      setError('Invalid admin password');
    }
  };

  const handleSaveStandard = async () => {
    if (!config) return;
    try {
      await saveConfig(config);
      setShowSaved(true);
      setTimeout(() => setShowSaved(false), 3000);
    } catch (e) {
      alert("Failed to save config.");
    }
  };

  const updateConfig = (section: keyof AppConfig, key: string, val: number) => {
    if (!config) return;
    setConfig({
      ...config,
      [section]: {
        ...(config[section] as any),
        [key]: val
      }
    });
  };

  const updateRoiVal = (idx: number, key: string, val: any) => {
    if (!config || !config.rois) return;
    const newRois = [...config.rois];
    newRois[idx] = { ...newRois[idx], [key]: val };
    setConfig({ ...config, rois: newRois });
  };

  const handleAddIntervention = () => {
    if (!newIntervention.trim()) return;
    const updatedProducts = products.map(p => {
      if (p.id === selectedProductId && !p.interventions.includes(newIntervention.trim())) {
        return { ...p, interventions: [...p.interventions, newIntervention.trim()] };
      }
      return p;
    });
    setProducts(updatedProducts);
    saveProducts(updatedProducts);
    setNewIntervention('');
  };

  const handleRemoveIntervention = (interventionToRemove: string) => {
    const updatedProducts = products.map(p => {
      if (p.id === selectedProductId) {
        return { ...p, interventions: p.interventions.filter(i => i !== interventionToRemove) };
      }
      return p;
    });
    setProducts(updatedProducts);
    saveProducts(updatedProducts);
  };

  const selectedProductObj = products.find(p => p.id === selectedProductId);
  const selectedRoi = config?.rois?.[selectedRoiIndex] as any;

  if (!isAuthenticated) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="bg-white p-8 rounded-2xl border border-[#e8e7ff] shadow-[0_2px_12px_rgba(78,71,255,0.08)] max-w-md w-full">
          <div className="flex justify-center mb-6">
            <div className="w-16 h-16 bg-[#F4F4F6] rounded-full flex items-center justify-center">
              <Lock className="w-8 h-8 text-[#4E47FF]" />
            </div>
          </div>
          <h2 className="text-2xl font-bold text-center text-[#232369] mb-2">Admin Access Required</h2>
          <p className="text-center text-gray-500 mb-6">Please enter the QA Admin password to access settings.</p>
          
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <input 
                type="password" 
                placeholder="Password"
                className="w-full p-3 border border-[#e8e7ff] rounded-xl focus:ring-2 focus:ring-[#4E47FF] outline-none bg-[#F4F4F6] text-[#232369]"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
            </div>
            <button 
              type="submit"
              className="w-full py-3 rounded-xl font-semibold text-white transition-all hover:-translate-y-0.5 shadow-md"
              style={{ background: 'linear-gradient(135deg, #6661FF, #4E47FF, #232369)' }}
            >
              Authenticate
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-[#232369] tracking-tight">Admin Settings</h1>
          <p className="text-[#6661FF] font-medium mt-1">Configure neural detection parameters and compliance limits.</p>
        </div>
        <div className="flex items-center space-x-3">
          {showSaved && (
            <span className="flex items-center space-x-1 text-green-600 font-medium bg-green-50 px-3 py-1 rounded-lg border border-green-200">
              <CheckCircle className="w-4 h-4" />
              <span>Saved via API</span>
            </span>
          )}
          <button 
            onClick={handleSaveStandard}
            className="flex items-center space-x-2 px-6 py-2.5 rounded-xl font-semibold text-white transition-all hover:-translate-y-0.5 shadow-md"
            style={{ background: 'linear-gradient(135deg, #6661FF, #4E47FF, #232369)' }}
          >
            <Lock className="w-4 h-4" />
            <span>Save as Media Fill Standard</span>
          </button>
        </div>
      </div>

      {!config ? (
        <div className="text-center text-gray-500 py-12 animate-pulse">Loading config from backend...</div>
      ) : (
      <div className="grid md:grid-cols-2 gap-6">
        {/* ROI Configuration */}
        <div className="bg-white rounded-2xl border border-[#e8e7ff] shadow-[0_2px_12px_rgba(78,71,255,0.08)] p-6 hover:-translate-y-1 transition-transform">
          <div className="flex items-center space-x-3 mb-4">
            <Settings className="w-6 h-6 text-[#4E47FF]" />
            <h3 className="text-xl font-bold text-[#232369]">ROI Configuration</h3>
          </div>
          <p className="text-sm text-gray-500 mb-6 italic bg-[#F4F4F6] p-3 rounded-lg border border-[#e8e7ff]">
            "Draw ROIs deeper inside the aseptic tank, beyond the physical glass opening, to avoid counting resting fingers as interventions."
          </p>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-[#232369] mb-1">Glove Port</label>
              <select className="w-full p-2 border border-[#e8e7ff] rounded-lg bg-[#F4F4F6] text-[#232369]" value={selectedRoiIndex} onChange={e => setSelectedRoiIndex(parseInt(e.target.value))}>
                {config.rois?.map((_, i) => (
                  <option key={i} value={i}>Port {i + 1}</option>
                ))}
              </select>
            </div>

            {selectedRoi && (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-[#232369] mb-1">Shape</label>
                    <select className="w-full p-2 border border-[#e8e7ff] rounded-lg bg-[#F4F4F6] text-[#232369]" value={selectedRoi.shape || 'circle'} onChange={e => updateRoiVal(selectedRoiIndex, 'shape', e.target.value)}>
                      <option value="circle">Circle</option>
                      <option value="ellipse">Ellipse</option>
                      <option value="polygon">Polygon</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[#232369] mb-1">Radius (px)</label>
                    <input type="number" value={selectedRoi.radius || 0} onChange={e => updateRoiVal(selectedRoiIndex, 'radius', parseInt(e.target.value))} className="w-full p-2 border border-[#e8e7ff] rounded-lg bg-[#F4F4F6] text-[#232369]" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-[#232369] mb-1">Center X</label>
                    <input type="number" value={selectedRoi.center?.[0] || 0} onChange={e => updateRoiVal(selectedRoiIndex, 'center', [parseInt(e.target.value), selectedRoi.center?.[1] || 0])} className="w-full p-2 border border-[#e8e7ff] rounded-lg bg-[#F4F4F6] text-[#232369]" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-[#232369] mb-1">Center Y</label>
                    <input type="number" value={selectedRoi.center?.[1] || 0} onChange={e => updateRoiVal(selectedRoiIndex, 'center', [selectedRoi.center?.[0] || 0, parseInt(e.target.value)])} className="w-full p-2 border border-[#e8e7ff] rounded-lg bg-[#F4F4F6] text-[#232369]" />
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Compliance Limits */}
        <div className="bg-white rounded-2xl border border-[#e8e7ff] shadow-[0_2px_12px_rgba(78,71,255,0.08)] p-6 hover:-translate-y-1 transition-transform">
          <div className="flex items-center space-x-3 mb-6">
            <ShieldAlert className="w-6 h-6 text-[#4E47FF]" />
            <h3 className="text-xl font-bold text-[#232369]">Compliance Limits</h3>
          </div>
          
          <div className="space-y-6">
            <SliderControl 
              label="Max Intervention Count" 
              min={1} max={50} step={1} 
              value={config.limits?.max_intervention_count || 20} 
              onChange={v => updateConfig('limits', 'max_intervention_count', v)} 
            />
            <SliderControl 
              label="Max Total Duration (s)" 
              min={60} max={1200} step={10} 
              value={config.limits?.max_total_duration_sec || 300} 
              onChange={v => updateConfig('limits', 'max_total_duration_sec', v)} 
            />
          </div>
        </div>

        {/* Detection Parameters */}
        <div className="bg-white rounded-2xl border border-[#e8e7ff] shadow-[0_2px_12px_rgba(78,71,255,0.08)] p-6 hover:-translate-y-1 transition-transform md:col-span-2">
          <div className="flex items-center space-x-3 mb-6">
            <Sliders className="w-6 h-6 text-[#4E47FF]" />
            <h3 className="text-xl font-bold text-[#232369]">Detection Parameters</h3>
          </div>
          
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            <SliderControl label="SSIM Threshold" min={0.01} max={0.5} step={0.01} value={config.detection?.ssim_threshold || 0.08} onChange={v => updateConfig('detection', 'ssim_threshold', v)} />
            <SliderControl label="EMA Beta" min={0.01} max={0.5} step={0.01} value={config.detection?.ema_beta || 0.2} onChange={v => updateConfig('detection', 'ema_beta', v)} />
            <SliderControl label="History Size" min={5} max={50} step={1} value={config.detection?.history_size || 25} onChange={v => updateConfig('detection', 'history_size', v)} />
            <SliderControl label="Min Motion Votes" min={1} max={25} step={1} value={config.detection?.min_motion_votes || 10} onChange={v => updateConfig('detection', 'min_motion_votes', v)} />
            <SliderControl label="Cooldown Frames" min={5} max={60} step={1} value={config.events?.cooldown_frames || 15} onChange={v => updateConfig('events', 'cooldown_frames', v)} />
            <SliderControl label="Min Active Frames" min={1} max={20} step={1} value={config.events?.min_active_frames || 5} onChange={v => updateConfig('events', 'min_active_frames', v)} />
            <SliderControl label="Min Intervention Duration (s)" min={0.1} max={10} step={0.1} value={config.events?.min_intervention_duration_sec || 2.0} onChange={v => updateConfig('events', 'min_intervention_duration_sec', v)} />
          </div>
        </div>

        {/* Product Intervention Type Manager */}
        <div className="bg-white rounded-2xl border border-[#e8e7ff] shadow-[0_2px_12px_rgba(78,71,255,0.08)] p-6 hover:-translate-y-1 transition-transform md:col-span-2">
          <div className="flex items-center space-x-3 mb-6">
            <Save className="w-6 h-6 text-[#4E47FF]" />
            <h3 className="text-xl font-bold text-[#232369]">Product Intervention Type Manager</h3>
          </div>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-[#232369] mb-1">Select Product</label>
              <select 
                className="w-full max-w-md p-2 border border-[#e8e7ff] rounded-lg bg-[#F4F4F6] text-[#232369]"
                value={selectedProductId}
                onChange={(e) => setSelectedProductId(e.target.value)}
              >
                {products.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
            
            <div className="bg-[#F4F4F6] p-4 rounded-xl border border-[#e8e7ff]">
              <h4 className="text-sm font-semibold text-[#232369] mb-3">Allowed Interventions</h4>
              <ul className="space-y-2 mb-4">
                {selectedProductObj?.interventions.map((int, idx) => (
                  <li key={idx} className="flex items-center justify-between bg-white p-2 rounded-lg border border-[#e8e7ff]">
                    <span className="text-sm text-gray-700">{int}</span>
                    <button 
                      onClick={() => handleRemoveIntervention(int)}
                      className="text-red-500 hover:text-red-700 text-sm font-medium px-2"
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
              <div className="flex space-x-2">
                <input 
                  type="text" 
                  placeholder="New intervention type..." 
                  className="flex-1 p-2 border border-[#e8e7ff] rounded-lg bg-white text-[#232369] outline-none focus:ring-2 focus:ring-[#4E47FF]" 
                  value={newIntervention}
                  onChange={(e) => setNewIntervention(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddIntervention()}
                />
                <button 
                  onClick={handleAddIntervention}
                  className="px-4 py-2 bg-[#4E47FF] text-white rounded-lg font-medium hover:bg-[#232369] transition-colors"
                >
                  Add
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      )}
    </div>
  );
}

function SliderControl({ label, min, max, step, value, onChange }: { label: string, min: number, max: number, step: number, value: number, onChange: (v: number) => void }) {
  return (
    <div>
      <div className="flex justify-between mb-2">
        <label className="text-sm font-medium text-[#232369]">{label}</label>
        <span className="text-sm font-bold text-[#4E47FF]">{Number.isInteger(value) ? value : value.toFixed(2)}</span>
      </div>
      <input 
        type="range" 
        min={min} 
        max={max} 
        step={step} 
        value={value} 
        onChange={(e) => onChange(parseFloat(e.target.value))} 
        className="w-full accent-[#4E47FF]" 
      />
    </div>
  );
}
