int unknown();
/*@ requires x > 0 && x < octant; */
void foo241(int octant, int x) {

    unsigned int count;
    int multFactor;
    int temp;
    int oddExp;
    int evenExp;
    int term;

    octant = 3.14159 / 3;
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