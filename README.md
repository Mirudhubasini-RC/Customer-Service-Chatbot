# Customer-Service-Chatbot
The AI-driven Customer Support Chatbot enhances retail by using NLP and ML to address queries, recommend products, and provide real-time support. It collects interaction data to deliver insights on customer preferences and trends, aiding retailers in making informed decisions and improving customer experience.


---

### Project Workflow: Initial Setup, Development, and Merge

**1. Cloning the Repository:**
   - The project repository was cloned from GitHub to the local machine using the command:

     git clone https://github.com/Mirudhubasini-RC/Customer-Service-Chatbot


**2. Node.js and npm Setup:**
   - Installed Node.js and npm packages by navigating to the project folder and running:
  
     npm install

   - This installed all the necessary dependencies listed in the `package.json` file for frontend development.

**3. Frontend Development:**
   - Created a separate Git branch for frontend development using:

     git checkout -b frontend

   - Built the frontend using React as a Progressive Web App (PWA). To enable PWA functionality, the service worker was modified from `unregister` to `register` in `src/serviceWorker.js`:

     serviceWorker.register();


**4. Backend Setup:**
   - In the `Backend` folder, created the `app.py` file for the Flask backend server.
   - Set up a Python virtual environment by running:

     python3 -m venv venv

   - Activated the virtual environment:

     source venv/bin/activate

   - Installed the required backend dependencies:

     pip install Flask Flask-CORS mysql-connector-python requests

   - Built the Flask server to handle API requests and database queries.

**5. Database Setup (MySQL on Mac):**
   - Installed MySQL on Mac using Homebrew:

     brew install mysql

   - Started the MySQL server:

     brew services start mysql

   - Logged in to the MySQL client:

     mysql -u root

   - Created the necessary database and tables for the project:
     
**6. Running the Server and Frontend:**
   - Both the Flask server and the React frontend were run:
     - To run the Flask server:

       python app.py

     - To run the React frontend:

       npm start


**7. Pushing and Merging the Code:**
   - After completing the frontend and backend work, changes were committed and pushed to the respective branches:

     git add .
     git commit -m "Completed frontend and backend development"
     git push origin frontend
     git push origin backend
     ```
   - Merged the branches into the main branch:

     git checkout main
     git merge frontend
     git merge backend

   - Resolved any merge conflicts, if necessary, and pushed the final merged code:

     git push origin main


**8. Final Steps:**
   - Verified that both frontend and backend work seamlessly together, including the integration with the MySQL database.
   - Cleaned up unnecessary branches:

     git branch -d frontend
     git branch -d backend


