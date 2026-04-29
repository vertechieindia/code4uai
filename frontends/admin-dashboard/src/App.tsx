/**
 * code4u.ai Admin Dashboard
 */
import React, { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { 
  OverviewPage, 
  TenantsPage, 
  ModelsPage, 
  AgentsPage,
  InfrastructurePage,
  SecurityPage,
  BillingPage,
  AnalyticsPage,
  SettingsPage,
  MCPPage,
  KnowledgePage,
  MobilePage
} from './pages';

export default function App() {
  const [activeItem, setActiveItem] = useState('overview');
  const [darkMode, setDarkMode] = useState(false);
  
  const renderPage = () => {
    switch (activeItem) {
      case 'overview':
        return <OverviewPage />;
      case 'tenants':
        return <TenantsPage />;
      case 'models':
        return <ModelsPage />;
      case 'agents':
        return <AgentsPage />;
      case 'mcp':
        return <MCPPage />;
      case 'knowledge':
        return <KnowledgePage />;
      case 'infrastructure':
        return <InfrastructurePage />;
      case 'security':
        return <SecurityPage />;
      case 'billing':
        return <BillingPage />;
      case 'analytics':
        return <AnalyticsPage />;
      case 'mobile':
        return <MobilePage />;
      case 'settings':
        return <SettingsPage />;
      default:
        return <OverviewPage />;
    }
  };

  return (
    <div className={`min-h-screen flex ${darkMode ? 'dark' : ''}`}>
      <Sidebar activeItem={activeItem} setActiveItem={setActiveItem} />
      
      <div className="flex-1 flex flex-col bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-white">
        <Header darkMode={darkMode} setDarkMode={setDarkMode} />
        
        <main className="flex-1 p-6 overflow-auto">
          {renderPage()}
        </main>
      </div>
    </div>
  );
}
