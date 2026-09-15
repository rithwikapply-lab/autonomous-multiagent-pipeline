import React from 'react';
import { CreditCard, Shield, Layers, Truck, AlertCircle } from 'lucide-react';

const PRESETS = [
  {
    label: 'Refund Policy SLA',
    query: 'How long do I have to request a refund?',
    icon: CreditCard,
    accent: 'from-cyan-500/20 to-blue-500/10 border-cyan-500/30 text-cyan-300 hover:border-cyan-400',
  },
  {
    label: 'Account Security',
    query: 'Is my password safe?',
    icon: Shield,
    accent: 'from-emerald-500/20 to-teal-500/10 border-emerald-500/30 text-emerald-300 hover:border-emerald-400',
  },
  {
    label: 'Pricing & Team Members',
    query: 'How many team members does the Pro plan support?',
    icon: Layers,
    accent: 'from-purple-500/20 to-indigo-500/10 border-purple-500/30 text-purple-300 hover:border-purple-400',
  },
  {
    label: 'Expedited Shipping',
    query: 'How much does expedited shipping cost?',
    icon: Truck,
    accent: 'from-amber-500/20 to-orange-500/10 border-amber-500/30 text-amber-300 hover:border-amber-400',
  },
  {
    label: 'Graceful Fallback (No-Info Demo)',
    query: 'What is your policy on cryptocurrency payments?',
    icon: AlertCircle,
    accent: 'from-rose-500/20 to-pink-500/10 border-rose-500/30 text-rose-300 hover:border-rose-400',
  },
];

export default function PresetQueries({ onSelect, disabled }) {
  return (
    <div className="w-full max-w-4xl mx-auto mt-3">
      <div className="flex items-center gap-2 mb-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
        <span>Try Example Queries</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {PRESETS.map((preset) => {
          const Icon = preset.icon;
          return (
            <button
              key={preset.query}
              onClick={() => onSelect(preset.query)}
              disabled={disabled}
              className={`group flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-gradient-to-r ${preset.accent} border transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none cursor-pointer`}
              title={preset.query}
            >
              <Icon className="w-3.5 h-3.5 transition-transform group-hover:rotate-6" />
              <span>{preset.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
