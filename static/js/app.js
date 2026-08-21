const form = document.getElementById("admissionForm");
const result = document.getElementById("result");

form.addEventListener("submit", async function (event) {
    event.preventDefault();

    const data = {
        student_name: document.getElementById("student_name").value,
        father_name: document.getElementById("father_name").value,
        mother_name: document.getElementById("mother_name").value,
        date_of_birth: document.getElementById("date_of_birth").value,
        gender: document.getElementById("gender").value,
        applying_class: document.getElementById("applying_class").value,
        previous_school: document.getElementById("previous_school").value,
        parent_cnic: document.getElementById("parent_cnic").value,
        phone: document.getElementById("phone").value,
        whatsapp: document.getElementById("whatsapp").value,
        email: document.getElementById("email").value,
        address: document.getElementById("address").value
    };

    result.className = "";
    result.style.display = "none";

    try {
        const response = await fetch("/api/admissions", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(data)
        });

        const responseData = await response.json();

        if (!response.ok) {
            throw new Error("Admission submission failed");
        }

        result.className = "result-success";
        result.innerHTML = `
            <strong>Application Submitted Successfully ✅</strong>
            <br><br>
            Application Number:
            <strong>${responseData.application_no}</strong>
            <br>
            Student: ${responseData.student_name}
            <br>
            Status: ${responseData.status}
        `;

        form.reset();
    } catch (error) {
        result.className = "result-error";
        result.innerHTML =
            "Something went wrong. Please check the server and try again.";
    }
});
