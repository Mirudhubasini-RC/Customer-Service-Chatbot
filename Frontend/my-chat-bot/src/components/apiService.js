const BASE_URL = 'http://localhost:8000'; // Base URL of your backend API

// Function to handle POST requests to the /query endpoint
export const sendQuery = async (query) => {
  try {
    const response = await fetch(`${BASE_URL}/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ query }),
    });

    if (!response.ok) {
      // Handle specific HTTP error codes if necessary
      const errorText = await response.text();
      throw new Error(`HTTP error! Status: ${response.status}, Message: ${errorText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error in sendQuery:', error);
    throw error; // Re-throw error to be caught by the calling function
  }
};

// Function to fetch sales data from /sales endpoint
export const fetchSalesData = async () => {
  try {
    const response = await fetch(`${BASE_URL}/sales`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      // Handle specific HTTP error codes if necessary
      const errorText = await response.text();
      throw new Error(`HTTP error! Status: ${response.status}, Message: ${errorText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error in fetchSalesData:', error);
    throw error; // Re-throw error to be caught by the calling function
  }
};

// Function to fetch queries data from /queries endpoint
export const fetchQueriesData = async () => {
  try {
    const response = await fetch(`${BASE_URL}/products`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      // Handle specific HTTP error codes if necessary
      const errorText = await response.text();
      throw new Error(`HTTP error! Status: ${response.status}, Message: ${errorText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error in fetchQueriesData:', error);
    throw error; // Re-throw error to be caught by the calling function
  }
};
