import React from 'react';
import { Users, Info } from 'lucide-react';

export function RoomOccupancy() {
  // Mock data for analytics
  const currentOccupancyCount = 3;
  const peopleInRoom = [
    { id: 1, name: 'John Doe', role: 'Operator' },
    { id: 2, name: 'Jane Smith', role: 'QA Inspector' },
    { id: 3, name: 'Mike Johnson', role: 'Supervisor' }
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-10">
      <header className="mb-2">
        <h1 className="text-3xl font-extrabold text-[#232369] tracking-tight">Room Occupancy</h1>
        <p className="text-[#6661FF] font-medium mt-1">Live monitoring and analytics of personnel inside the aseptic room.</p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Live Feed Section */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#e8e7ff]">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-[#232369]">Door Camera Live Feed</h3>
              <div className="flex items-center space-x-2">
                <span className="relative flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
                </span>
                <span className="text-xs font-bold text-red-600 uppercase tracking-widest">Live</span>
              </div>
            </div>
            
            <div className="aspect-video bg-[#1a1a2e] rounded-xl border-2 border-gray-800 flex items-center justify-center relative overflow-hidden">
              <div className="text-gray-400 flex flex-col items-center">
                <Info className="w-12 h-12 mb-2 opacity-50" />
                <p className="text-lg font-medium">Video Feed Unavailable</p>
                <p className="text-sm opacity-70">Awaiting stream connection...</p>
              </div>
            </div>
          </div>
        </div>

        {/* Analytics Section */}
        <div className="space-y-6">
          <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#e8e7ff]">
            <h3 className="text-sm font-semibold text-[#6661FF] uppercase tracking-wider mb-2">Current Occupancy</h3>
            <div className="flex items-end space-x-3">
              <span className="text-5xl font-black text-[#232369]">{currentOccupancyCount}</span>
              <span className="text-lg font-medium text-gray-500 mb-1">people</span>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#e8e7ff]">
            <h3 className="text-sm font-semibold text-[#6661FF] uppercase tracking-wider mb-4">Personnel in Room</h3>
            <div className="space-y-3">
              {peopleInRoom.map(person => (
                <div key={person.id} className="flex items-center space-x-3 p-3 bg-[#F4F4F6] rounded-xl border border-transparent hover:border-[#4E47FF]/20 transition-colors">
                  <div className="w-10 h-10 rounded-full bg-[#4E47FF]/10 flex items-center justify-center text-[#4E47FF] font-bold">
                    {person.name.charAt(0)}
                  </div>
                  <div>
                    <h4 className="font-semibold text-[#232369] text-sm">{person.name}</h4>
                    <p className="text-xs text-gray-500">{person.role}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
