document.getElementById("origin").textContent = new URL(browser.runtime.getURL("/")).origin;
browser.runtime.sendMessage({ type: "jeff:bridge-health" }).then((status) => {
  const element = document.getElementById("privacy-status");
  if (status.reachable && status.ok && status.ollama_local) element.textContent = "Local only: Ollama is reachable on this computer.";
  else if (status.reachable && status.ok) element.textContent = "Privacy warning: chat and selected page text go to " + status.ollama_url + ".";
  else element.textContent = "The local bridge or Ollama is not reachable. Check Jeff settings and start the bridge.";
  if (status.reachable && status.ok && !status.chat_model_available) {
    element.textContent += " The selected chat model “" + status.chat_model + "” is not installed.";
  }
}).catch(() => {
  document.getElementById("privacy-status").textContent = "The local bridge could not be checked.";
});
