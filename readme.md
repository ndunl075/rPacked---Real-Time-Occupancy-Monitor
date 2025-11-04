rPacked: A Live RPAC Capacity Tracker

This project is a full-stack, automated web application that scrapes and displays the live capacity for Ohio State University's RPAC (Recreation and Physical Activity Center).

It provides a clean, mobile-friendly, real-time dashboard to see how busy different areas are before you go.

Tech Stack

This project was built using a modern, serverless, and automated stack.

Backend & Automation

Python: The core language for all data scraping and backend logic.

Selenium: Used to "headless" browse the dynamic, JavaScript-powered Rec Sports website.

BeautifulSoup4: Used to parse the HTML and extract the capacity data.

Firebase Admin SDK (Python): A secure, backend-only library used to write the scraped data directly into the Firestore database.

Database

Google Firestore: A NoSQL, real-time cloud database used to store the capacity data. The frontend connects to this directly.

Frontend

HTML5: For the core page structure.

Tailwind CSS: A utility-first CSS framework for building the responsive, mobile-first design.

JavaScript (ES6+): Used to connect to Firebase, fetch data in real-time, and dynamically render the capacity cards.

Firebase JS SDK: The client-side library used to authenticate and create a live, real-time connection (onSnapshot) to the Firestore database.

CI/CD & Platform

GitHub Actions: Used as a CI/CD tool to run the Python scraper on an automated schedule (e.g., every 15 minutes).

Firebase Platform (BaaS): Used as the core "Backend-as-a-Service," providing the database, user authentication (anonymous), and hosting.

Netlify / Firebase Hosting: Used to deploy and host the static front-end web application.

How It Works

This project has two main parts that work together:

The Scraper (Automated Backend):

A GitHub Actions workflow is scheduled to run every 15 minutes.

It spins up a new server, installs Python, and runs the scraper.py script.

The script uses a secret Service Account Key (stored in GitHub Secrets) to securely sign in to Firebase as an admin.

It uses Selenium to open the RPAC website, let the JavaScript load, and then grabs the HTML.

It parses the HTML to find the "open" status, "current," and "total" capacity for each location.

It writes this data to a single document in the Firestore database.

The Web App (Frontend):

A user opens the index.html file (hosted on Netlify or Firebase).

The JavaScript in the file uses the public firebaseConfig to connect to the project.

It signs the user in anonymously (to satisfy security rules).

It attaches a real-time onSnapshot listener to the one database document.

When the data is loaded (or when the scraper updates it), the page instantly re-renders the cards to show the new numbers.

How to Set This Up Yourself

Clone this repository.

Create your own Firebase Project:

Create a new project in the Firebase Console.

Go to Firestore Database and create a database (in (default) mode).

Go to Authentication and enable the Anonymous sign-in provider.

Go to your Project Settings > Service Accounts and generate a new private key. This will download your serviceAccountKey.json file.

Go to your Project Settings > General and register a new Web App (</>). Copy the firebaseConfig object it gives you.

Set up the Frontend:

Paste your firebaseConfig object into public/index.html.

Deploy the public/ folder to Netlify or Firebase Hosting.

Set up the Backend:

In your Google Cloud Console, make sure the "Cloud Firestore API" and "Identity Toolkit API" are enabled.

In your GitHub repository, go to Settings > Secrets > Actions and create a new secret named FIREBASE_SERVICE_ACCOUNT.

Paste the entire contents of your serviceAccountKey.json file into this secret.

Run the "Run RPAC Scraper" action from your "Actions" tab to populate your database for the first time.