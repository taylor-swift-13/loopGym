int unknown();
/*@ requires x > octant1 && x < octant2; */
void foo242(int octant1, int octant2, int x) {

    unsigned int count;
    int multFactor;
    int temp;
    int oddExp;
    int evenExp;
    int term;

    octant1 = 0;
    octant2 = 3.14159 / 8;
    oddExp = x;
    evenExp = 1.0;
    term = x;
    count = 2;
    multFactor = 0;


    while(unknown()){
       term = term * (x / count);

       if((count / 2) % 2 == 0)
       multFactor = 1;
       else
       multFactor = -1;

       evenExp = evenExp + multFactor * term;

       count = count + 1;

       term = term * (x / count);

       oddExp = oddExp + multFactor * term;

       count = count + 1;
      }

    /*@ assert oddExp >= evenExp; */

  }