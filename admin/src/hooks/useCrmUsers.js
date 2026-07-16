import { useState, useEffect, useCallback } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const useCrmUsers = () => {
  const [crmUsers, setCrmUsers] = useState([]);

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/users`);
        if (res.ok) {
          const data = await res.json();
          const mappedUsers = data.map(user => ({
            id: user.user_id,
            businessName: user.business_name,
            password: user.password || '',
            virtualNumber: user.exotel_virtual_number || '',
            assignedAgent: 'Unassigned',
            status: 'Active',
            created_at: '2026-05-30'
          }));
          setCrmUsers(mappedUsers);
        }
      } catch (err) {
        console.error("Failed to fetch CRM users from DB:", err);
      }
    };
    fetchUsers();
  }, []);

  const addCrmUser = async (newUser) => {
    try {
      const payload = {
        user_id: newUser.userId,
        business_name: newUser.businessName,
        password: newUser.password,
        exotel_virtual_number: newUser.virtualNumber
      };

      const res = await fetch(`${API_BASE_URL}/api/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const createdUser = await res.json();
        const user = {
          id: createdUser.user_id,
          businessName: createdUser.business_name,
          password: createdUser.password || '',
          virtualNumber: createdUser.exotel_virtual_number || '',
          assignedAgent: 'Unassigned',
          status: 'Active',
          created_at: new Date().toISOString().split('T')[0]
        };
        setCrmUsers(prev => [user, ...prev]);
      }
    } catch (err) {
      console.error("Failed to add CRM user:", err);
    }
  };

  const deleteCrmUser = async (userId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/users/${userId}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        setCrmUsers(prev => prev.filter(u => u.id !== userId));
      }
    } catch (err) {
      console.error("Failed to delete CRM user:", err);
    }
  };

  const updateCrmUser = (userId, updatedFields) => {
    setCrmUsers(prev => prev.map(u => {
      if (u.id === userId) {
        return { ...u, ...updatedFields };
      }
      return u;
    }));
  };

  const getAvailableExotelNumbers = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/exotel/available-numbers`);
      if (res.ok) {
        const data = await res.json();
        return data.numbers || [];
      } else {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to fetch numbers from Exotel");
      }
    } catch (err) {
      console.error("Error fetching available Exotel numbers:", err);
      throw err;
    }
  }, []);

  return {
    crmUsers, setCrmUsers,
    addCrmUser, deleteCrmUser, updateCrmUser,
    getAvailableExotelNumbers
  };
};
