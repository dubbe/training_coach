import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const historikDir = path.join(__dirname, '..', '..', 'historik');
const outputFilePath = path.join(__dirname, '..', 'public', 'database.json');

const parseStrengthWorkout = (content, date) => {
    const lines = content.split('\n');
    const title = lines[0].replace('# ', '').replace(`(${date})`, '').trim();
    const exercises = [];
    let currentExercise = null;

    for (const line of lines) {
        if (line.startsWith('## ')) {
            if (currentExercise) {
                exercises.push(currentExercise);
            }
            currentExercise = { name: line.replace('## ', '').trim(), sets: [] };
        } else if (line.startsWith('### ')) { // Handles exercises under a '## Styrketräning' heading
             if (currentExercise) {
                exercises.push(currentExercise);
            }
            currentExercise = { name: line.replace('### ', '').trim(), sets: [] };
        }
        
        else if (line.trim().startsWith('*   Set') && currentExercise) {
            currentExercise.sets.push(line.trim().replace('*   Set ', ''));
        }
    }
    if (currentExercise) {
        exercises.push(currentExercise);
    }

    return {
        id: date + '-' + title.replace(/ /g, '-'),
        date,
        title,
        type: 'Styrka',
        exercises: exercises.filter(e => e.name !== 'Plyometrics' && e.name !== 'Kondition' && e.name !== 'Sammanfattning'),
    };
};

const parseRunningWorkout = (content, date) => {
    const titleMatch = content.match(/# Löppass: (.*) \(/);
    const title = titleMatch ? titleMatch[1] : 'Löpning';

    const metrics = {};
    const lines = content.split('\n');
    for (const line of lines) {
        if (line.startsWith('|')) {
            const parts = line.split('|').map(s => s.trim());
            if (parts.length > 2 && parts[1] !== 'Metric' && parts[1] !== '-----------------') {
                const key = parts[1].replace(/\s+/g, '_').toLowerCase();
                metrics[key] = parts[2];
            }
        }
    }

    return {
        id: date + '-' + title.replace(/ /g, '-'),
        date,
        title,
        type: 'Löpning',
        metrics,
    };
};

const parseFootballWorkout = (content, date) => {
    const metrics = {};
    const lines = content.split('\n');
    for (const line of lines) {
        if (line.startsWith('|')) {
            const parts = line.split('|').map(s => s.trim());
            if (parts.length > 2 && parts[1] !== 'Metric' && parts[1] !== '-----------------') {
                const key = parts[1].replace(/\s+/g, '_').toLowerCase();
                metrics[key] = parts[2];
            }
        }
    }
    return {
        id: date + '-Fotboll',
        date,
        title: 'Fotbollsträning',
        type: 'Fotboll',
        metrics,
    };
};


const main = () => {
    try {
        const filenames = fs.readdirSync(historikDir);
        const workouts = [];

        for (const filename of filenames) {
            if (path.extname(filename) === '.md') {
                const filePath = path.join(historikDir, filename);
                const content = fs.readFileSync(filePath, 'utf-8');
                const date = (filename.match(/(\d{4}-\d{2}-\d{2})/) || [])[0];

                if (!date) {
                    console.warn(`Skipping file without date in filename: ${filename}`);
                    continue;
                }

                let workoutData;
                if (filename.includes('_Löpning')) {
                    workoutData = parseRunningWorkout(content, date);
                } else if (filename.includes('Fotbollsträning')) {
                    workoutData = parseFootballWorkout(content, date);
                } else {
                    workoutData = parseStrengthWorkout(content, date);
                }
                workouts.push(workoutData);
            }
        }

        // Sort workouts by date, descending
        workouts.sort((a, b) => new Date(b.date) - new Date(a.date));

        fs.writeFileSync(outputFilePath, JSON.stringify(workouts, null, 2));
        console.log(`Successfully built database with ${workouts.length} workouts.`);

    } catch (error) {
        console.error("Error building the data:", error);
    }
};

main();
