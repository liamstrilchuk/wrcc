window.addEventListener("load", renderDashboard);

async function renderDashboard() {
	const contestName = location.href.split("/").pop();
	const response = await fetch("/api/dashboard/" + contestName);
	const data = await response.json();
	const container = document.getElementById("container");
	const numQuestions = data.questions.length;
	let tableHTML = "<table style='margin-top: 15px;'><tr><th>User</th>"

	for (let i = 0; i < numQuestions; i++) {
		tableHTML += "<th>#" + (i + 1) + "</th>";
	}
	tableHTML += "<th>Total Score</th></tr>";
	let rows = [];

	for (const user in data.user_questions) {
		let totalUserScore = 0, totalAttempted = 0;
		let row = `<tr><td>${user}</td>`;
		for (let i = 0; i < numQuestions; i++) {
			const points = data.questions[i].point_value;
			totalAttempted += attempted = data.user_questions[user][i][1];
			totalUserScore += increase = data.user_questions[user][i][0] * points / 100;
			row += `<td style="background: ${bgColor(increase, points, attempted)};"></td>`;
		}
		row += `<td>${totalUserScore}</td></tr>`;
		rows.push([ totalUserScore, row, totalAttempted ]);
	}

	rows = rows.sort((a, b) => (b[0] - a[0]) * 1e6 + (b[2] - a[2]));
	for (const row of rows) {
		tableHTML += row[1];
	}

	container.innerHTML = tableHTML;

	window.setTimeout(renderDashboard, 20000);
}

function bgColor(earned, total, attempted) {
	return earned === total ? "#87ff85" : (earned === 0 ? (attempted ? "#ff9791" : "") : "#e7ff61");
}
