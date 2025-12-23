import { useState } from 'react';
import { Activity, FileText, BarChart3, Calendar } from 'lucide-react';
import { DashboardLive } from './pages/DashboardLive';
import { EventsLogs } from './pages/EventsLogs';
import { Reports } from './pages/Reports';
import { Planning } from './pages/Planning';

type Page = 'dashboard' | 'events' | 'reports' | 'planning';

function App() {
  const [currentPage, setCurrentPage] = useState<Page>('dashboard');

  const navigation = [
    { id: 'dashboard' as Page, name: 'Dashboard Live', icon: Activity },
    { id: 'events' as Page, name: 'Events & Logs', icon: FileText },
    { id: 'reports' as Page, name: 'Reports', icon: BarChart3 },
    { id: 'planning' as Page, name: 'Planning', icon: Calendar },
  ];

  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              <div className="flex-shrink-0 flex items-center">
                <h1 className="text-xl font-bold text-gray-900">
                  TECPAP Scheduler
                </h1>
              </div>
              <div className="hidden sm:ml-8 sm:flex sm:space-x-4">
                {navigation.map((item) => {
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.id}
                      onClick={() => setCurrentPage(item.id)}
                      className={`inline-flex items-center px-3 py-2 text-sm font-medium transition-colors ${
                        currentPage === item.id
                          ? 'border-b-2 border-blue-600 text-blue-600'
                          : 'text-gray-600 hover:text-gray-900'
                      }`}
                    >
                      <Icon className="w-4 h-4 mr-2" />
                      {item.name}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        <div className="sm:hidden border-t">
          <div className="flex overflow-x-auto">
            {navigation.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => setCurrentPage(item.id)}
                  className={`flex-1 flex flex-col items-center px-3 py-2 text-xs font-medium ${
                    currentPage === item.id
                      ? 'border-b-2 border-blue-600 text-blue-600 bg-blue-50'
                      : 'text-gray-600'
                  }`}
                >
                  <Icon className="w-5 h-5 mb-1" />
                  {item.name}
                </button>
              );
            })}
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {currentPage === 'dashboard' && <DashboardLive />}
        {currentPage === 'events' && <EventsLogs />}
        {currentPage === 'reports' && <Reports />}
        {currentPage === 'planning' && <Planning />}
      </main>

      <footer className="bg-white border-t mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <p className="text-center text-sm text-gray-500">
            TECPAP Scheduler - Real-time Production Simulation Control
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
