window.addEventListener("load", async () => {
	const container = document.getElementById("contestContainer");
	const response = await fetch("/api/contests");
	const contests = (await response.json()).contests;

	contests.forEach(contest => {
		const startDate = new Date(contest.start_date * 1000);
		const endDate = new Date(contest.end_date * 1000);

		const dashboardLink = window.userIsAdmin ? `&bull; <a href="/dashboard/${contest.short_name}">Dashboard</a>` : "";
		const changeTimesLink = window.userIsAdmin ? `&bull; <a href="/change-times/${contest.short_name}">Change times</a>` : "";
		const submissionsLink = window.userIsAdmin ? `&bull; <a href="/submissions/${contest.short_name}">Submissions</a>` : "";

		container.innerHTML += `
			<div class="contest">
				<div class="contest-name">${contest.name} (${contest.individual ? "individual" : "team"})</div>
				<div class="contest-date">${formatDate(startDate)} to ${formatDate(endDate)}</div>
				<div class="contest-link"><a href="/contest/${contest.short_name}">View</a> ${dashboardLink} ${changeTimesLink} ${submissionsLink}</div>
			</div>
		`;
	});
});
