import React, { useState, useEffect, useCallback } from 'react';
import { Plus, Trash2, Edit2 } from 'lucide-react';
import type { Property } from '../types';

interface PropertiesTabProps {
  currentUser: { user_id: string; business_name: string };
  searchQuery: string;
  refreshTrigger: number;
}

export function PropertiesTab({ currentUser, searchQuery, refreshTrigger }: PropertiesTabProps) {
  const [properties, setProperties] = useState<Property[]>([]);
  const [showAddPropertyForm, setShowAddPropertyForm] = useState(false);
  const [newPropHeading, setNewPropHeading] = useState('');
  const [newPropDesc, setNewPropDesc] = useState('');

  // State for inline editing
  const [editingPropertyId, setEditingPropertyId] = useState<number | null>(null);
  const [editPropHeading, setEditPropHeading] = useState('');
  const [editPropDesc, setEditPropDesc] = useState('');

  const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  // Fetch properties from database via FastAPI
  const loadProperties = useCallback(async () => {
    if (!currentUser) return;
    try {
      const response = await fetch(`${API_BASE_URL}/api/properties?user_id=${currentUser.user_id}`);
      if (response.ok) {
        const data = await response.json();
        const mapped = data.map((item: any, idx: number) => ({
          id: item.id,
          sequence: idx + 1,
          name: `Property #${idx + 1}`,
          property_heading: item.property_heading || `Property #${idx + 1}`,
          type: "Listing",
          price: "On Request",
          location: "Lansdowne",
          description: item.property_details,
          status: "Available"
        }));
        setProperties(mapped);
      }
    } catch (error) {
      console.error("Failed to load properties:", error);
    }
  }, [currentUser]);

  useEffect(() => {
    loadProperties();
  }, [loadProperties, refreshTrigger]);

  // Property addition handler
  const handleAddProperty = async (heading: string, description: string) => {
    if (!currentUser) return;
    try {
      const response = await fetch(`${API_BASE_URL}/api/properties`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ property_heading: heading, property_details: description, user_id: currentUser.user_id })
      });
      if (response.ok) {
        await loadProperties();
      } else {
        alert("Failed to save property to database.");
      }
    } catch (error) {
      console.error("Error adding property:", error);
    }
  };

  // Property removal handler
  const handleDeleteProperty = async (id: number) => {
    if (confirm("Are you sure you want to remove this property?")) {
      try {
        const response = await fetch(`${API_BASE_URL}/api/properties/${id}`, {
          method: "DELETE"
        });
        if (response.ok) {
          await loadProperties();
        } else {
          alert("Failed to delete property from database.");
        }
      } catch (error) {
        console.error("Error deleting property:", error);
      }
    }
  };

  // Property editing handler
  const handleEditProperty = async (id: number, heading: string, description: string) => {
    if (!currentUser) return;
    try {
      const response = await fetch(`${API_BASE_URL}/api/properties/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ property_heading: heading, property_details: description, user_id: currentUser.user_id })
      });
      if (response.ok) {
        await loadProperties();
      } else {
        alert("Failed to update property in database.");
      }
    } catch (error) {
      console.error("Error updating property:", error);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPropHeading.trim()) {
      alert("Please enter property heading.");
      return;
    }
    if (!newPropDesc.trim()) {
      alert("Please enter property details/description.");
      return;
    }
    handleAddProperty(newPropHeading, newPropDesc);
    setNewPropHeading('');
    setNewPropDesc('');
    setShowAddPropertyForm(false);
  };

  const handleEditSubmit = (id: number) => {
    if (!editPropHeading.trim()) {
      alert("Property heading cannot be empty.");
      return;
    }
    if (!editPropDesc.trim()) {
      alert("Property description cannot be empty.");
      return;
    }
    handleEditProperty(id, editPropHeading, editPropDesc);
    setEditingPropertyId(null);
    setEditPropHeading('');
    setEditPropDesc('');
  };

  const startEditing = (prop: Property) => {
    setEditingPropertyId(prop.id);
    setEditPropHeading(prop.property_heading || '');
    setEditPropDesc(prop.description);
  };

  const filteredProperties = properties.filter(p =>
    p.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div>
      <div className="properties-header-actions">
        <div>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Sequenced Real Estate Holdings</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            View and construct properties portfolio sequentially.
          </p>
        </div>

        <button
          className="btn-add-property"
          onClick={() => setShowAddPropertyForm(prev => !prev)}
        >
          <Plus size={18} />
          <span>{showAddPropertyForm ? 'Collapse Editor' : 'Add Property'}</span>
        </button>
      </div>

      {/* Add Property TextBox Form */}
      {showAddPropertyForm && (
        <div className="add-property-section">
          <form onSubmit={handleSubmit} className="add-property-form">
            <h4 style={{ fontWeight: 600, marginBottom: '8px' }}>
              Create Property Sequence #{properties.length + 1}
            </h4>

            <div className="form-group" style={{ marginBottom: '16px' }}>
              <label>Property Heading</label>
              <input
                type="text"
                className="form-control"
                placeholder="e.g. 2BHK in Connaught Place"
                value={newPropHeading}
                onChange={(e) => setNewPropHeading(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label>Property Description / Specifications</label>
              <textarea
                className="form-control form-textarea"
                placeholder="Enter property details, specifications, green area coverage, dimensions..."
                value={newPropDesc}
                onChange={(e) => setNewPropDesc(e.target.value)}
                style={{ minHeight: '120px' }}
                required
              />
            </div>

            <div className="form-buttons">
              <button
                type="button"
                className="btn-cancel"
                onClick={() => setShowAddPropertyForm(false)}
              >
                Cancel
              </button>
              <button type="submit" className="btn-submit">
                Save & Append Sequence
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Grid of properties */}
      <div className="properties-grid">
        {filteredProperties.length > 0 ? (
          filteredProperties.map((prop) => (
            <div className="property-card" key={prop.id}>
              <span className="property-sequence">
                {prop.sequence.toString().padStart(2, '0')}
              </span>

              {editingPropertyId === prop.id ? (
                <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="Property Heading"
                    value={editPropHeading}
                    onChange={(e) => setEditPropHeading(e.target.value)}
                    required
                  />
                  <textarea
                    className="form-control form-textarea"
                    value={editPropDesc}
                    onChange={(e) => setEditPropDesc(e.target.value)}
                    style={{ minHeight: '120px', fontSize: '0.875rem' }}
                    required
                  />
                  <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                    <button
                      className="btn-cancel"
                      onClick={() => setEditingPropertyId(null)}
                      style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                    >
                      Cancel
                    </button>
                    <button
                      className="btn-submit"
                      onClick={() => handleEditSubmit(prop.id)}
                      style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                    >
                      Save
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <h4 style={{ margin: '0 0 8px 0', fontSize: '1rem', color: 'var(--text-main)' }}>
                    {prop.property_heading}
                  </h4>
                  <p className="property-details" style={{
                    fontSize: '0.875rem',
                    lineHeight: 1.5,
                    whiteSpace: 'pre-wrap',
                    color: 'var(--text-secondary)',
                    display: '-webkit-box',
                    WebkitLineClamp: 4,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden'
                  }}>
                    {prop.description}
                  </p>

                  <div className="property-actions" style={{ marginTop: 'auto', paddingTop: '12px', display: 'flex', gap: '8px' }}>
                    <button
                      className="action-btn"
                      onClick={() => startEditing(prop)}
                      title="Edit property"
                      style={{ color: 'var(--text-secondary)' }}
                    >
                      <Edit2 size={14} />
                    </button>
                    <button
                      className="action-btn delete-btn"
                      onClick={() => handleDeleteProperty(prop.id)}
                      title="Remove property"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </>
              )}
            </div>
          ))
        ) : (
          <div style={{ gridColumn: '1/-1', textAlign: 'center', padding: '48px', color: 'var(--text-secondary)' }}>
            No properties matched search query.
          </div>
        )}
      </div>
    </div>
  );
}
