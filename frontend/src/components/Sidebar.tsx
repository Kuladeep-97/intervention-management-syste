import React from 'react';
import { Activity, Settings, BarChart2, Clock, User } from 'lucide-react';
import { getProducts } from '../constants';
import { Stage } from '../App';

export function Sidebar({ currentStage, onNavigate, product, batch }: { currentStage: Stage, onNavigate: (s: Stage) => void, product: string | null, batch: string | null }) {
  const products = getProducts();
  const productName = products.find(p => p.id === product)?.name || 'Unknown Product';

  return (
    <aside className="w-64 bg-white border-r border-[#e8e7ff] flex flex-col h-full shadow-[0_2px_12px_rgba(78,71,255,0.08)]">
      <div className="p-6 border-b border-[#e8e7ff]">
        <h2 className="text-2xl font-bold text-[#232369] tracking-tight">Dheera AI</h2>
        <p className="text-xs font-semibold text-[#6661FF] tracking-widest mt-1 uppercase">Intervention Management System</p>
      </div>

      <div className="p-4">
        <div className="bg-[#4E47FF]/10 rounded-xl p-3 border border-[#4E47FF]/20">
          <p className="text-xs text-[#6661FF] font-medium mb-1">Current Session</p>
          <p className="text-sm font-semibold text-[#232369] truncate" title={productName}>{productName}</p>
          <div className="inline-block mt-2 px-2 py-1 bg-[#4E47FF] text-white text-xs rounded-md font-medium">
            {batch || 'No Batch'}
          </div>
        </div>
      </div>

      <nav className="flex-1 px-4 space-y-2 mt-4">
        <button 
          onClick={() => onNavigate('dashboard')}
          className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-colors ${currentStage === 'dashboard' ? 'bg-[#F4F4F6] text-[#4E47FF] font-semibold' : 'text-gray-600 hover:bg-[#F4F4F6] hover:text-[#232369]'}`}
        >
          <Activity className="w-5 h-5" />
          <span>Live Dashboard</span>
        </button>
        <button 
          onClick={() => onNavigate('analytics')}
          className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-colors ${currentStage === 'analytics' ? 'bg-[#F4F4F6] text-[#4E47FF] font-semibold' : 'text-gray-600 hover:bg-[#F4F4F6] hover:text-[#232369]'}`}
        >
          <BarChart2 className="w-5 h-5" />
          <span>Analytics</span>
        </button>
        <button 
          onClick={() => onNavigate('admin')}
          className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-colors ${currentStage === 'admin' ? 'bg-[#F4F4F6] text-[#4E47FF] font-semibold' : 'text-gray-600 hover:bg-[#F4F4F6] hover:text-[#232369]'}`}
        >
          <Settings className="w-5 h-5" />
          <span>Admin Settings</span>
        </button>
        <button 
          onClick={() => onNavigate('room_occupancy')}
          className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-colors ${currentStage === 'room_occupancy' ? 'bg-[#F4F4F6] text-[#4E47FF] font-semibold' : 'text-gray-600 hover:bg-[#F4F4F6] hover:text-[#232369]'}`}
        >
          <User className="w-5 h-5" />
          <span>Room Occupancy</span>
        </button>
      </nav>

      <div className="p-4 border-t border-[#e8e7ff] text-sm text-gray-500">
        <div className="flex items-center space-x-2 mb-2">
          <Clock className="w-4 h-4" />
          <span>{new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
        </div>
        <div className="flex items-center space-x-2">
          <User className="w-4 h-4" />
          <span>QA Operator</span>
        </div>
      </div>
    </aside>
  );
}
