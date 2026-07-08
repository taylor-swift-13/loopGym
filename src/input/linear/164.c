int unknown();
/*@ requires n > 0; */
void foo164(int n) {

    int b;
    int j;
    int flag;

    j = 0;
    b = 0;


        flag = unknown();

    while(b < n){
       if(flag == 1){
       j = j + 1;
       b = b + 1;
      }
       else if (flag != 1){
       b = b + 1;
      }
      }

    /*@ assert (j != n) ==> (flag != 1); */

  }