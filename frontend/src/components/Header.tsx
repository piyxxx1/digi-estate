import { Search } from 'lucide-react';
import { useLocation } from 'react-router-dom';

interface HeaderProps {
  searchQuery: string;
  setSearchQuery: (query: string) => void;
}

export function Header({ searchQuery, setSearchQuery }: HeaderProps) {
  const location = useLocation();
  const path = location.pathname;

  const getTitle = () => {
    switch (path) {
      case '/':
        return 'CRM Dashboard Overview';
      case '/properties':
        return 'Properties Directory';
      case '/leads':
        return 'Leads & Inbound Profiles';
      case '/calls':
        return 'AI Call Center Analytics';
      default:
        return 'DigiCRM';
    }
  };

  return (
    <header className="crm-header">
      <div className="crm-header-title">
        <h2>{getTitle()}</h2>
      </div>

      <div className="crm-header-actions">
        <div className="crm-search-bar">
          <Search className="crm-search-icon" size={16} />
          <input
            type="text"
            placeholder="Search CRM logs..."
            className="crm-search-input"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>
    </header>
  );
}
