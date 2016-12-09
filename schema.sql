CREATE TABLE 'industries' ('id' INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, 'name' TEXT NOT NULL);
CREATE TABLE userCompany (
  idUser INTEGER, 
  idCompany INTEGER,
  FOREIGN KEY(idUser) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY(idCompany) REFERENCES company(id) ON DELETE CASCADE
);
CREATE TABLE userIndustry (
  idUser INTEGER, 
  idIndustry INTEGER,
  FOREIGN KEY(idUser) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY(idIndustry) REFERENCES industries(id) ON DELETE CASCADE
);
CREATE TABLE 'companies' ('id' INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,'name' TEXT NOT NULL, 'ticker' TEXT);
CREATE TABLE 'geographies' ('id' INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,'name' TEXT NOT NULL);
CREATE TABLE users
( id INTEGER PRIMARY KEY AUTOINCREMENT,
email TEXT NOT NULL,
hash TEXT NOT NULL
);
CREATE TABLE userGeography (
  idUser INTEGER, 
  idGeography INTEGER,
  FOREIGN KEY(idUser) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY(idGeography) REFERENCES geographies(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX unique_user_company on userCompany(idUser, idCompany);
CREATE UNIQUE INDEX unique_user_industry on userIndustry(idUser, idIndustry);
CREATE UNIQUE INDEX unique_user_geography on userGeography(idUser, idGeography);
