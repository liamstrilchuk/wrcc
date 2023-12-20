window.addEventListener("load", renderDashboard);

async function renderDashboard() {
	const response = await fetch("/api/leaderboard");
	const data = await response.json();
	const container = document.getElementById("leaderboardContainer");
	let tableHTML = "<table style='margin-top: 15px;'><tr><th>Place</th><th>Team</th><th>Total Score</th></tr>";

	for (let i = 0; i < Math.min(data.length, 10); i++) {
		tableHTML += `<tr><td>${i + 1}</td><td>${data[i][0]}</td><td>${data[i][1]}</td></tr>`;
	}

	container.innerHTML = tableHTML + "</table>";

	window.setTimeout(renderDashboard, 20000);
}