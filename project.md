This file is initializer instructor of my project. I will explain general purpose of project and architecture. After, i will plan technical needs with you step by step.

# CONSTRUCTION
- This is ai first and ai native project. 
- An ai first development environment will help to develop this project.
- AI-first development will be carried out using an agent harness such as OpenCode.

# CONTENT
- This project is posture recognition and oratory skills enhancer.
- Project will be 2 part. First posture recognition and second oratory skills enhancer.
- These 2 parts will be versioned. I will be explain main structure of posture recognition. Oratory skills part will be explained later. Because of preventing confusion, building will continue step by step.

	# Posture Recognition
	- Posture recognition's aims is catching person's posture and if desk worker's posture is not upright while he is staying at PC, warning.
	- Posture recognition also consist of 2 parts. Parts' architecture are described separately below
	- First part name is Recognition
	  All processes of this part will be developing using YOLO's version 26 ai model
	  Check camera permissions
	  YOLO will catch person's posture using device's camera
	  First,  detect person 
	  Second, estimate pose keypoints, human's movement
	  Finally, YOLO will capture the user's posture from their real-time movements
	  There will be a calculation that score person's posture. As mentioned before, detail will be explained step by step
	  App will track this calculation and if score is not in valid range for specific time, it will trigger and event.
	  
	  
	  Recognition will be Jupyter notebook project. So, there will be ipynb file
	  Jupyter notebook environment will be using for development. When development finishes, it will be replaced to py project.
	  App will be Windows only and local. 
	  App will not store any data.

	- Second part is Warning
	  This part will warn user.
	  WPF launches the Python engine as a child process and communication is event-only via JSON-lines over stdout. Python runs YOLO pose scoring locally and prints only bad_posture, recovered, heartbeat and error events with no data stored. WPF reads stdout asynchronously.
	  App will pop-up warning screen.
	  Warning screen will be full window.
	  There will be configuration and according to this config, if mousing blocking switch is enabled, app will also block mouse movement
	  Mouse blocking event will be disabled pressing ESC keyboard button
	  I will explain technical details step by step
	  
	  
	  Warning will be C#, .NET 12, WPF project

	# Warning
	- Project will be C#, .NET 12, WPF project
	- It will fire when Posture Recognition event triggers bad_posture event
	- It will work from background but the application will be started manually.
	- There will be 2 features
	- First feature is warning message 
	  It will pop-up a message above everything
	  There will be configuration flag which name is IS_WARNING_WINDOW_CLOSABLE. If it is true user can close window. If false, user can't
	- Message window design properties described below
	  Screen with flashing text and borders
	  FLashing should be below 3Hz
	  At the very top, the text "STAND TALL!!!" in capital letters
	  Below that, centered, the image "kyphosis.jpg" located in this folder
	- Second feature is blocking mouse events
	  User can't control movement, wheel, left and right click events.
	  There will be configuration flag which name is IS_MOUSE_EVENTS_ENABLED. If it is true, system will block mouse events. If it is false, system won't block mouse events
	  There will be failsafe condition if engine dies mid-block
	- If recovery event triggers from Posture Recognition side, message will close and user can use mouse events again
	  