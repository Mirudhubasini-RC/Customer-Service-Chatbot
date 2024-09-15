// apiService.js
const API_URL = 'http://localhost:8000';

export const fetchSalesData = async () => {
  try {
    const response = await fetch(`${API_URL}/sales`);
    if (!response.ok) {
      throw new Error('Network response was not ok');
    }
    return await response.json();
  } catch (error) {
    console.error('Error fetching sales data:', error);
    throw error;
  }
};

export const fetchQueries = async () => {
  try {
    const response = await fetch(`${API_URL}/queries`);
    if (!response.ok) {
      throw new Error('Network response was not ok');
    }
    return await response.json();
  } catch (error) {
    console.error('Error fetching queries:', error);
    throw error;
  }
};

export const sendQuery = async (query) => {
  try {
    const response = await fetch(`${API_URL}/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ query }),
    });
    if (!response.ok) {
      throw new Error('Network response was not ok');
    }
    return await response.json();
  } catch (error) {
    console.error('Error sending query:', error);
    throw error;
  }
};
