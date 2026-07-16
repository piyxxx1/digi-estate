import React, { useState } from 'react';
import { useAdmin } from '../context/AdminContext';
import { 
  Users, 
  Search, 
  UserPlus, 
  Play, 
  Trash2, 
  Key, 
  Eye, 
  EyeOff, 
  PhoneCall, 
  Bot, 
  Info,
  Layers,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';

const UserAssignment = () => {
  const { crmUsers, agents, addCrmUser, deleteCrmUser, triggerCall, getAvailableExotelNumbers } = useAdmin();
  
  // State
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const [showAddModal, setShowAddModal] = useState(false);
  const [revealedPasswords, setRevealedPasswords] = useState({});
  
  // Form fields for new CRM user
  const [newUserId, setNewUserId] = useState('');
  const [newBusinessName, setNewBusinessName] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newVirtualNumber, setNewVirtualNumber] = useState('');
  const [formError, setFormError] = useState('');

  // States for dynamic Exotel virtual number fetching
  const [availableExotelNumbers, setAvailableExotelNumbers] = useState([]);
  const [isLoadingNumbers, setIsLoadingNumbers] = useState(false);
  const [fetchError, setFetchError] = useState('');

  React.useEffect(() => {
    if (!showAddModal) return;

    const fetchNumbers = async () => {
      setIsLoadingNumbers(true);
      setFetchError('');
      try {
        const numbers = await getAvailableExotelNumbers();
        // Filter out already assigned numbers
        const unassignedNumbers = numbers.filter(
          num => !crmUsers.some(user => user.virtualNumber === num.phone_number)
        );
        
        setAvailableExotelNumbers(unassignedNumbers);
        if (unassignedNumbers.length > 0) {
          setNewVirtualNumber(unassignedNumbers[0].phone_number);
        } else {
          setNewVirtualNumber('');
        }
      } catch (err) {
        setFetchError(err.message || 'Failed to fetch owned ExoPhones from Exotel.');
        setAvailableExotelNumbers([]);
        setNewVirtualNumber('');
      } finally {
        setIsLoadingNumbers(false);
      }
    };

    fetchNumbers();
  }, [showAddModal, crmUsers, getAvailableExotelNumbers]);

  // Filter CRM Users
  const filteredUsers = crmUsers.filter(user => {
    const matchesSearch = user.id.toLowerCase().includes(searchTerm.toLowerCase()) || 
                          user.businessName.toLowerCase().includes(searchTerm.toLowerCase()) || 
                          user.virtualNumber.includes(searchTerm);
    const matchesStatus = statusFilter === 'All' || user.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const togglePasswordReveal = (userId) => {
    setRevealedPasswords(prev => ({
      ...prev,
      [userId]: !prev[userId]
    }));
  };

  const handleCreateCrmUser = (e) => {
    e.preventDefault();
    setFormError('');

    if (!newUserId || !newBusinessName || !newPassword || !newVirtualNumber) {
      setFormError('Please fill in all mandatory fields.');
      return;
    }

    if (crmUsers.some(user => user.businessName.toLowerCase() === newBusinessName.trim().toLowerCase())) {
      setFormError(`Business name "${newBusinessName.trim()}" is already registered.`);
      return;
    }
    
    if (crmUsers.some(user => user.id.toLowerCase() === newUserId.trim().toLowerCase())) {
      setFormError(`User ID "${newUserId.trim()}" is already taken.`);
      return;
    }

    if (crmUsers.some(user => user.virtualNumber === newVirtualNumber)) {
      setFormError(`The Exotel Virtual Number ${newVirtualNumber} is already assigned to another user.`);
      return;
    }

    // Submit CRM user
    addCrmUser({
      userId: newUserId.trim(),
      businessName: newBusinessName,
      password: newPassword,
      virtualNumber: newVirtualNumber
    });

    // Reset Form
    setNewUserId('');
    setNewBusinessName('');
    setNewPassword('');
    setNewVirtualNumber('');
    setShowAddModal(false);
  };

  return (
    <div className="page-content">
      <div>
        {/* CRM Users Table Card */}
        <div className="search-filter-bar">
          <div className="search-input-wrapper">
            <Search size={16} />
            <input 
              type="text" 
              className="input-field" 
              placeholder="Search CRM Users by ID, business name, virtual number..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          <select 
            className="select-field" 
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="All">All Statuses</option>
            <option value="Active">Active</option>
            <option value="Suspended">Suspended</option>
          </select>

          <button 
            className="btn btn-primary"
            onClick={() => {
              setFormError('');
              setShowAddModal(true);
            }}
          >
            <UserPlus size={16} />
            <span>Add CRM User</span>
          </button>
        </div>

        {/* CRM Users Table Card */}
        <div className="glass-card">
          <div className="card-header" style={{ marginBottom: '1.25rem' }}>
            <div className="card-title">
              <Layers size={18} style={{ color: 'var(--zoho-blue)' }} />
              <span>Active CRM Allocations ({filteredUsers.length})</span>
            </div>
          </div>

          <div className="table-wrapper">
            <table className="custom-table">
              <thead>
                <tr>
                  <th>User ID</th>
                  <th>Business Name</th>
                  <th>Virtual Number (Exotel)</th>
                  <th>CRM Password</th>
                  <th>Status</th>
                  <th style={{ textAlign: 'right' }}>Telemetry Sim</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.length === 0 ? (
                  <tr>
                    <td colSpan="6" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                      No CRM users found matching current filter query.
                    </td>
                  </tr>
                ) : (
                  filteredUsers.map(user => (
                    <tr key={user.id}>
                      <td style={{ fontWeight: 700, color: 'var(--zoho-blue)', textTransform: 'none' }}>{user.id}</td>
                      <td style={{ fontWeight: 600 }}>{user.businessName}</td>
                      <td>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--zoho-teal)' }}>
                          {user.virtualNumber}
                        </span>
                      </td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }}>
                            {revealedPasswords[user.id] ? user.password : '••••••••'}
                          </span>
                          <button 
                            type="button"
                            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'inline-flex' }}
                            onClick={() => togglePasswordReveal(user.id)}
                            title={revealedPasswords[user.id] ? "Hide password" : "Show password"}
                          >
                            {revealedPasswords[user.id] ? <EyeOff size={14} /> : <Eye size={14} />}
                          </button>
                        </div>
                      </td>
                      <td>
                        <span className="badge badge-success">
                          {user.status}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                          <button 
                            type="button"
                            className="icon-btn call-trigger"
                            onClick={() => triggerCall(user.virtualNumber, true)}
                            title={`Simulate inbound call to ${user.businessName} (${user.virtualNumber})`}
                          >
                            <PhoneCall size={12} />
                          </button>
                          <button 
                            type="button"
                            className="icon-btn"
                            style={{ color: 'var(--zoho-red)', borderColor: 'rgba(226, 60, 60, 0.2)', background: 'var(--zoho-red-light)' }}
                            onClick={() => deleteCrmUser(user.id)}
                            title="Revoke CRM Account"
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Add CRM User Modal */}
      {showAddModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-title">
              <UserPlus size={20} style={{ color: 'var(--zoho-blue)' }} />
              <h3>Add CRM User Account</h3>
            </div>

            {formError && (
              <div style={{ background: 'var(--zoho-red-light)', border: '1px solid rgba(226, 60, 60, 0.2)', padding: '0.75rem', borderRadius: '8px', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--zoho-red)', fontSize: '0.8rem' }}>
                <AlertCircle size={16} />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleCreateCrmUser}>
              <div className="form-group">
                <label className="form-label">User Email ID</label>
                <input 
                  type="email" 
                  className="input-field" 
                  style={{ paddingLeft: '0.75rem' }}
                  required
                  placeholder="name@company.com"
                  value={newUserId}
                  onChange={(e) => setNewUserId(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Business Name</label>
                <input 
                  type="text" 
                  className="input-field" 
                  style={{ paddingLeft: '0.75rem' }}
                  required
                  placeholder="e.g. Acme Corp"
                  value={newBusinessName}
                  onChange={(e) => setNewBusinessName(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">CRM Password</label>
                <input 
                  type="text" 
                  className="input-field" 
                  style={{ paddingLeft: '0.75rem' }}
                  required
                  placeholder="Set account password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Assign Exotel Virtual Number</label>
                {isLoadingNumbers ? (
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem', background: 'var(--bg-light)', borderRadius: '6px' }}>
                    <span className="status-dot pulsing" style={{ backgroundColor: 'var(--zoho-blue)' }}></span>
                    <span>Querying Exotel Account API for owned ExoPhones...</span>
                  </div>
                ) : fetchError ? (
                  <div style={{ fontSize: '0.8rem', color: 'var(--zoho-red)', padding: '0.5rem', background: 'var(--zoho-red-light)', borderRadius: '6px' }}>
                    Error: {fetchError}
                  </div>
                ) : availableExotelNumbers.length === 0 ? (
                  <div style={{ fontSize: '0.8rem', color: 'var(--zoho-red)', padding: '0.5rem', background: 'var(--zoho-red-light)', borderRadius: '6px' }}>
                    Warning: No ExoPhones found in your Exotel account. Please ensure you have purchased numbers in Exotel.
                  </div>
                ) : (
                  <select 
                    className="select-field"
                    style={{ width: '100%' }}
                    value={newVirtualNumber}
                    onChange={(e) => setNewVirtualNumber(e.target.value)}
                  >
                    {availableExotelNumbers.map(item => (
                      <option key={item.phone_number} value={item.phone_number}>
                        {item.friendly_name || item.phone_number} {item.rental_price && item.rental_price !== "0.000000" ? `($${item.rental_price}/mo)` : ''}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div className="form-actions">
                <button 
                  type="button" 
                  className="btn btn-secondary" 
                  onClick={() => setShowAddModal(false)}
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  className="btn btn-primary"
                  disabled={isLoadingNumbers || availableExotelNumbers.length === 0}
                  style={{ opacity: (isLoadingNumbers || availableExotelNumbers.length === 0) ? 0.5 : 1 }}
                >
                  Provision CRM User
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserAssignment;
