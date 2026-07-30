import { useEffect } from "react";
import "./App.css";

function App() {
  useEffect(() => {
    window.location.replace("HOSTELFRONTEND.html");
  }, []);

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontFamily: "'Space Grotesk', sans-serif",
      color: "#674bb5",
      background: "#f7f9fb"
    }}>
      Loading UniNest Hostel...
    </div>
  );
}

export default App;