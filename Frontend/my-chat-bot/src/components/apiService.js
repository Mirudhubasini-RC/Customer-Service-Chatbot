// apiService.js
const API_URL = 'http://localhost:8000/query'; // URL of your backend API

export const sendQuery = async (query) => {
  try {
    const response = await fetch(API_URL, {
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
