const mealDate = document.getElementById('meal-date').value;
const form = document.getElementById('add-meal-form');

form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const nameInput = document.getElementById('meal-name');
    const calInput = document.getElementById('meal-calories');
    const name = nameInput.value.trim();
    const calories = parseInt(calInput.value);

    if (!name || isNaN(calories) || calories < 0) return;

    const res = await fetch('/api/meals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date: mealDate, name, calories })
    });

    if (res.ok) {
        const meal = await res.json();
        addMealToList(meal);
        form.reset();
        nameInput.focus();
        updateTotal();
        hideEmptyState();
    }
});

function addMealToList(meal) {
    const list = document.getElementById('meal-list');
    const div = document.createElement('div');
    div.className = 'meal-item';
    div.dataset.id = meal.id;

    const infoDiv = document.createElement('div');
    infoDiv.className = 'meal-info';

    const nameSpan = document.createElement('span');
    nameSpan.className = 'meal-name';
    nameSpan.textContent = meal.name;

    const calSpan = document.createElement('span');
    calSpan.className = 'meal-calories';
    calSpan.textContent = meal.calories + ' cal';

    infoDiv.appendChild(nameSpan);
    infoDiv.appendChild(calSpan);

    const actionsDiv = document.createElement('div');
    actionsDiv.className = 'meal-actions';
    actionsDiv.innerHTML =
        `<button class="btn-edit" onclick="editMeal(${meal.id})">Edit</button>` +
        `<button class="btn-delete" onclick="deleteMeal(${meal.id})">Delete</button>`;

    div.appendChild(infoDiv);
    div.appendChild(actionsDiv);
    list.appendChild(div);
}

async function deleteMeal(id) {
    if (!confirm('delete this meal?')) return;

    const res = await fetch(`/api/meals/${id}`, { method: 'DELETE' });
    if (res.ok) {
        const el = document.querySelector(`.meal-item[data-id="${id}"]`);
        if (el) el.remove();
        updateTotal();
        checkEmptyState();
    }
}

function editMeal(id) {
    const el = document.querySelector(`.meal-item[data-id="${id}"]`);
    const nameEl = el.querySelector('.meal-name');
    const calEl = el.querySelector('.meal-calories');

    const currentName = nameEl.textContent;
    const currentCal = parseInt(calEl.textContent);

    // Store originals for cancel
    el.dataset.originalName = currentName;
    el.dataset.originalCal = currentCal;

    // Build edit inputs safely (no innerHTML with user data)
    const infoDiv = el.querySelector('.meal-info');
    infoDiv.innerHTML = '';

    const nameInput = document.createElement('input');
    nameInput.type = 'text';
    nameInput.className = 'edit-name';
    nameInput.value = currentName;

    const calInput = document.createElement('input');
    calInput.type = 'number';
    calInput.className = 'edit-calories';
    calInput.value = currentCal;
    calInput.min = '0';

    infoDiv.appendChild(nameInput);
    infoDiv.appendChild(calInput);

    el.querySelector('.meal-actions').innerHTML =
        `<button class="btn-save" onclick="saveMeal(${id})">Save</button>` +
        `<button class="btn-cancel" onclick="cancelEdit(${id})">Cancel</button>`;

    nameInput.focus();
}

async function saveMeal(id) {
    const el = document.querySelector(`.meal-item[data-id="${id}"]`);
    const name = el.querySelector('.edit-name').value.trim();
    const calories = parseInt(el.querySelector('.edit-calories').value);

    if (!name || isNaN(calories) || calories < 0) return;

    const res = await fetch(`/api/meals/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, calories })
    });

    if (res.ok) {
        const meal = await res.json();
        restoreMealDisplay(el, meal);
        updateTotal();
    }
}

function cancelEdit(id) {
    const el = document.querySelector(`.meal-item[data-id="${id}"]`);
    const name = el.dataset.originalName;
    const calories = parseInt(el.dataset.originalCal);
    restoreMealDisplay(el, { id, name, calories });
}

function restoreMealDisplay(el, meal) {
    const infoDiv = el.querySelector('.meal-info');
    infoDiv.innerHTML = '';

    const nameSpan = document.createElement('span');
    nameSpan.className = 'meal-name';
    nameSpan.textContent = meal.name;

    const calSpan = document.createElement('span');
    calSpan.className = 'meal-calories';
    calSpan.textContent = meal.calories + ' cal';

    infoDiv.appendChild(nameSpan);
    infoDiv.appendChild(calSpan);

    el.querySelector('.meal-actions').innerHTML =
        `<button class="btn-edit" onclick="editMeal(${meal.id})">Edit</button>` +
        `<button class="btn-delete" onclick="deleteMeal(${meal.id})">Delete</button>`;
}

async function updateTotal() {
    const res = await fetch(`/api/meals/${mealDate}`);
    if (res.ok) {
        const data = await res.json();
        document.getElementById('daily-total').textContent = data.total + ' cal';
    }
}

function hideEmptyState() {
    const empty = document.getElementById('empty-state');
    if (empty) empty.style.display = 'none';
}

function checkEmptyState() {
    const items = document.querySelectorAll('.meal-item');
    const empty = document.getElementById('empty-state');
    if (items.length === 0 && empty) {
        empty.style.display = '';
    }
}
