/**
 * Vanguard Gym OS - Core Client Utilities
 */

document.addEventListener("DOMContentLoaded", () => {
  // Mobile sidebar navigation toggle
  const sidebar = document.querySelector(".app-sidebar");
  const backdrop = document.querySelector(".sidebar-backdrop");
  const toggleBtn = document.querySelector(".mobile-menu-toggle");

  if (toggleBtn && sidebar && backdrop) {
    toggleBtn.addEventListener("click", () => {
      sidebar.classList.toggle("open");
      backdrop.classList.toggle("open");
    });

    backdrop.addEventListener("click", () => {
      sidebar.classList.remove("open");
      backdrop.classList.remove("open");
    });
  }

  // Keyboard shortcut: Escape closes all open modals
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      document.querySelectorAll(".modal-overlay.open").forEach((modal) => {
        modal.classList.remove("open");
      });
    }
  });

  // Modal backdrop click close
  document.querySelectorAll(".modal-overlay").forEach((overlay) => {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        overlay.classList.remove("open");
      }
    });
  });
});

// Modal Global Functions
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.add("open");
    const firstInput = modal.querySelector("input, select, textarea");
    if (firstInput) firstInput.focus();
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove("open");
  }
}

// Global Toast System
function showToast(message, type = "info") {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      z-index: 9999;
      display: flex;
      flex-direction: column;
      gap: 10px;
      max-width: 380px;
    `;
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = `alert alert-${type} animate-slide-up`;
  toast.style.cssText = "box-shadow: 0 4px 16px rgba(0,0,0,0.5); margin: 0;";
  toast.innerHTML = `
    <span>${message}</span>
    <button style="background:none; border:none; color:inherit; cursor:pointer; margin-left:12px; font-weight:bold;" onclick="this.parentElement.remove()">✕</button>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 4500);
}

// Client-side quick table search filter
function filterTable(inputId, tableId) {
  const input = document.getElementById(inputId);
  const table = document.getElementById(tableId);
  if (!input || !table) return;

  const filter = input.value.toLowerCase();
  const rows = table.querySelectorAll("tbody tr");

  rows.forEach((row) => {
    const text = row.textContent.toLowerCase();
    row.style.display = text.includes(filter) ? "" : "none";
  });
}
