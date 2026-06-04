import React, { useState } from 'react';
import { SelectionScreen } from './components/SelectionScreen';
import { Dashboard } from './components/Dashboard';
import { AdminSettings } from './components/AdminSettings';
import { Analytics } from './components/Analytics';
import { Sidebar } from './components/Sidebar';
import { RoomOccupancy } from './components/RoomOccupancy';

export type Stage = 'selection' | 'dashboard' | 'admin' | 'analytics' | 'room_occupancy';

export default function App() {
  const [currentStage, setCurrentStage] = useState<Stage>('selection');
  const [selectedProduct, setSelectedProduct] = useState<string | null>(null);
  const [selectedBatch, setSelectedBatch] = useState<string | null>(null);

  if (currentStage === 'selection') {
    return (
      <SelectionScreen 
        onProceed={(product, batch) => {
          setSelectedProduct(product);
          setSelectedBatch(batch);
          setCurrentStage('dashboard');
        }} 
      />
    );
  }

  return (
    <div className="flex h-screen bg-[#F4F4F6] text-[#232369] font-sans">
      <Sidebar 
        currentStage={currentStage} 
        onNavigate={setCurrentStage} 
        product={selectedProduct} 
        batch={selectedBatch} 
      />
      <main className="flex-1 overflow-auto p-6">
        {currentStage === 'dashboard' && <Dashboard product={selectedProduct} batch={selectedBatch} onNavigate={setCurrentStage} />}
        {currentStage === 'admin' && <AdminSettings product={selectedProduct} />}
        {currentStage === 'analytics' && <Analytics product={selectedProduct} batch={selectedBatch} onNavigate={setCurrentStage} />}
        {currentStage === 'room_occupancy' && <RoomOccupancy />}
      </main>
    </div>
  );
}
