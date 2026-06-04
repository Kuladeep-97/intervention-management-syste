import React, { useState } from 'react';
import { getProducts } from '../constants';
import { ShieldCheck, Zap } from 'lucide-react';

export function SelectionScreen({ onProceed }: { onProceed: (product: string, batch: string) => void }) {
  const [product, setProduct] = useState('');
  const [batch, setBatch] = useState('');

  const products = getProducts();
  const selectedProductObj = products.find(p => p.id === product);

  return (
    <div className="min-h-screen bg-[#F4F4F6] flex flex-col items-center justify-center p-4 font-sans">
      <div className="max-w-3xl w-full space-y-8">
        <div className="text-center">
          <h1 className="text-5xl font-bold tracking-tight text-[#232369] mb-4">
            Dheera AI
          </h1>
          <p className="text-xl text-[#6661FF]">
            Intervention Management System for Aseptic Tanks
          </p>
        </div>


        <div className="bg-white p-8 rounded-2xl border border-[#e8e7ff] shadow-[0_2px_12px_rgba(78,71,255,0.08)]">
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-[#232369] mb-2">Select Product</label>
              <select 
                className="w-full p-3 border border-[#e8e7ff] rounded-xl focus:ring-2 focus:ring-[#4E47FF] focus:border-transparent outline-none bg-[#F4F4F6] text-[#232369]"
                value={product}
                onChange={(e) => {
                  setProduct(e.target.value);
                  setBatch('');
                }}
              >
                <option value="">-- Choose a Product --</option>
                {products.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>

            {product && (
              <div>
                <label className="block text-sm font-medium text-[#232369] mb-2">Select Batch</label>
                <select 
                  className="w-full p-3 border border-[#e8e7ff] rounded-xl focus:ring-2 focus:ring-[#4E47FF] focus:border-transparent outline-none bg-[#F4F4F6] text-[#232369]"
                  value={batch}
                  onChange={(e) => setBatch(e.target.value)}
                >
                  <option value="">-- Choose a Batch --</option>
                  {selectedProductObj?.batches.map(b => (
                    <option key={b} value={b}>{b}</option>
                  ))}
                </select>
              </div>
            )}

            <button
              disabled={!product || !batch}
              onClick={() => onProceed(product, batch)}
              className="w-full py-4 rounded-xl font-semibold text-white text-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:-translate-y-0.5 shadow-lg"
              style={{ background: 'linear-gradient(135deg, #6661FF, #4E47FF, #232369)' }}
            >
              Start Monitoring Session →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
