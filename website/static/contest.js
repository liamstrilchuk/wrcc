window.addEventListener("load", async () => {
	const contestName = location.href.split("/").pop();
	const container = document.getElementById("questionContainer");
	const response = await fetch("/api/contest/" + contestName);
	const contest = (await response.json()).contest;
	let tableHTML = `
		<table>
			<tr>
				<th>Question #</th>
				<th>Question Name</th>
				<th>Link</th>
				<th>Status</th>
				<th>Points Earned</th>
			</tr>
	`;
	document.getElementById("contestName").innerHTML = contest.name;
	document.title = contest.name + " - Waterloo Region Computing Contest";
	const totalPoints = contest.questions.reduce((acc, val) => acc + val.point_value, 0);
	const earnedPoints = contest.questions.reduce((acc, val) => acc + val.point_value * val.percent_earned / 100, 0);

	contest.questions.forEach((question, index) => {
		tableHTML += `
			<tr class="question">
				<td>#${index + 1}</td>
				<td>${question.name}</td>
				<td><a href="/contest/${contestName}/question/${question.short_name}">View</a></td>
				<td>${question.percent_earned === 100 ? "Complete" : (question.percent_earned === 0 ? "Not complete" : "Partially complete")}</td>
				<td>${Math.floor(question.point_value / 100 * question.percent_earned)}/${question.point_value}</td>
			</tr>
		`;
	});

	tableHTML += `
		<tr>
			<td></td><td></td><td></td><td></td>
			<td><b>${earnedPoints}/${totalPoints}</b></td>
		</tr></table>`;
	container.innerHTML = tableHTML;

	let submissionsTable = `
		<h2>Submissions</h2>
		<table>
			<tr>
				<th>Question Name</th>
				<th>Time submitted</th>
				<th>Status</th>
				<th>Verdict</th>
				<th>Code</th>
			</tr>
	`;
	const sresponse = await fetch("/api/submissions/" + contestName);
	const submissions = (await sresponse.json()).submissions;

	submissions.forEach(submission => {
		const time = new Date(submission.timestamp * 1000);
		submissionsTable += `
			<tr class="submission">
				<td>${submission.question}</td>
				<td>${formatDate(time)}</td>
				<td>${submission.status}</td>
				<td>${submission.verdict}</td>
				<td><a href="/submission/${submission.id}">View</a></td>
			</tr>
		`;
	});

	submissionsTable += "</table>";
	container.innerHTML += submissionsTable;
});
